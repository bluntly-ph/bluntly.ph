"""A "day" and a "month" here mean Manila ones.

bluntly is Philippines-specific, so any calendar date a person would recognise
has to be derived in Asia/Manila. Absolute instants stay UTC; this is only about
turning them into dates.

Two bugs came from getting that wrong, and they were opposite halves of the same
mistake:

  * `PriceObservationIn.observed_at` compared against a UTC `date.today()`, so
    for eight hours of every day (Manila 00:00–07:59) a reader entering the
    price they paid *today* was told it was in the future.

  * `commission_service` derived `cycle_month` from a UTC date while
    `honesty_fund_service.previous_cycle_month` derived its cycle in Manila —
    and the fund pools commissions by that exact column. A commission timestamped
    2026-08-31 18:00 UTC is 2026-09-01 02:00 in Manila: tagged August, expected
    in September. If August had already been distributed, that share was money
    the fund never paid out.

The timezone was declared in three places and agreed in none of them. It now
lives in `app/core/constants.py`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.constants import MANILA
from app.services.honesty_fund_service import previous_cycle_month

# Manila is UTC+8, so these instants are the previous UTC day and the next
# Manila day — the window where the two calendars disagree.
BOUNDARY_INSTANTS = [
    datetime(2026, 8, 31, 16, 0, tzinfo=UTC),   # 2026-09-01 00:00 Manila
    datetime(2026, 8, 31, 18, 30, tzinfo=UTC),  # 2026-09-01 02:30 Manila
    datetime(2026, 8, 31, 23, 59, tzinfo=UTC),  # 2026-09-01 07:59 Manila
    datetime(2025, 12, 31, 20, 0, tzinfo=UTC),  # 2026-01-01 04:00 Manila (year end)
]


def cycle_month_for(stamp: datetime) -> date:
    """The derivation commission_service performs, isolated."""
    occurred = stamp.astimezone(MANILA).date()
    return date(occurred.year, occurred.month, 1)


class TestTheTimezoneHasOneDefinition:

    def test_manila_is_utc_plus_eight(self):
        offset = datetime(2026, 6, 1, 12, tzinfo=UTC).astimezone(MANILA).utcoffset()
        assert offset == timedelta(hours=8)

    def test_it_does_not_observe_daylight_saving(self):
        """The fallback offset is exact only because this holds."""
        for month in (1, 4, 7, 10):
            stamp = datetime(2026, month, 15, 12, tzinfo=UTC)
            assert stamp.astimezone(MANILA).utcoffset() == timedelta(hours=8)


class TestCommissionsLandInTheCycleTheFundExpects:

    @pytest.mark.parametrize("stamp", BOUNDARY_INSTANTS)
    def test_the_cycle_month_follows_the_manila_calendar(self, stamp):
        manila_day = stamp.astimezone(MANILA).date()
        assert cycle_month_for(stamp) == date(manila_day.year, manila_day.month, 1)

    @pytest.mark.parametrize("stamp", BOUNDARY_INSTANTS)
    def test_it_disagrees_with_the_utc_answer(self, stamp):
        """Proves these instants actually exercise the bug rather than passing
        for free — a UTC derivation gives a different month for every one."""
        utc_month = date(stamp.year, stamp.month, 1)
        assert cycle_month_for(stamp) != utc_month

    def test_the_fund_and_the_commissions_agree_on_the_boundary(self):
        """The fund distributes the *previous* Manila month. A commission from
        the first hours of this Manila month must not fall into it."""
        now = datetime(2026, 9, 1, 2, 0, tzinfo=UTC).astimezone(MANILA)
        distributing = previous_cycle_month(now)          # August
        just_earned = cycle_month_for(datetime(2026, 8, 31, 18, 0, tzinfo=UTC))
        assert just_earned == date(2026, 9, 1)
        assert just_earned != distributing, (
            "a commission earned in September would be pooled into the August "
            "cycle, which is being distributed now")


class TestUserFacingDatesUseManila:

    def test_a_price_paid_today_in_manila_is_accepted(self):
        """The eight-hour window where UTC still says yesterday."""
        from decimal import Decimal

        from app.models.enums import Platform
        from app.schemas.product import PriceObservationIn, _ph_today

        today = _ph_today()
        assert PriceObservationIn(platform=Platform.shopee, price=Decimal("100"),
                                  observed_at=today).observed_at == today

    def test_tomorrow_is_still_refused(self):
        from decimal import Decimal

        from pydantic import ValidationError

        from app.models.enums import Platform
        from app.schemas.product import PriceObservationIn, _ph_today

        with pytest.raises(ValidationError):
            PriceObservationIn(platform=Platform.shopee, price=Decimal("100"),
                               observed_at=_ph_today() + timedelta(days=1))

    def test_the_manila_date_is_never_behind_the_utc_one(self):
        """UTC+8 means Manila is the same day or the next one, never earlier."""
        from app.schemas.product import _ph_today
        assert _ph_today() >= datetime.now(UTC).date()


def test_commission_service_really_derives_it_this_way():
    """`cycle_month_for` above is a copy, so pin the original.

    The wiring is where the bug was — the arithmetic was never wrong, it was
    fed a UTC date.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app" / "services" / "commission_service.py").read_text(encoding="utf-8")
    assert "stamp.astimezone(MANILA).date()" in src, (
        "commission_service no longer derives the cycle month in Manila; it "
        "will disagree with honesty_fund_service across a month boundary")


def test_no_service_derives_a_calendar_date_from_utc_directly():
    """`datetime.now(UTC).date()` is a Manila-day question answered in UTC."""
    import pathlib
    import re

    services = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    offenders = []
    for path in services.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"datetime\.now\(UTC\)\.date\(\)|date\.today\(\)", line):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, (
        f"{offenders} derive a calendar date from UTC. If it is a date a person "
        f"would recognise, use MANILA; if it is an instant, keep the datetime.")
