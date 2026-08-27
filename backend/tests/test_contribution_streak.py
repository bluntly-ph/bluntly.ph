"""The Insights contribution streak (frame 5762:752).

Owner decision: the streak counts days the reviewer CONTRIBUTED, never days
they visited. These are pure tests of the rules — no database, no clock — so
the semantics are pinned independently of how the dates are fetched.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.services.contribution_streak import (
    contribution_calendar,
    streak_from_dates,
    today_in_manila,
)

TODAY = date(2026, 8, 27)
D = lambda n: TODAY - timedelta(days=n)  # noqa: E731 - reads better in tables


# The rules ------------------------------------------------------------------

def test_no_activity_is_zero_not_an_error():
    assert streak_from_dates([], TODAY) == 0


def test_one_day_today():
    assert streak_from_dates([TODAY], TODAY) == 1


def test_multiple_contributions_on_one_day_count_once():
    """Three reviews in an afternoon is one active day, not three."""
    assert streak_from_dates([TODAY, TODAY, TODAY], TODAY) == 1


def test_consecutive_days():
    assert streak_from_dates([D(0), D(1), D(2), D(3)], TODAY) == 4


def test_a_missed_day_ends_the_streak():
    """D(2) is missing, so the run stops there and the older block is ignored."""
    assert streak_from_dates([D(0), D(1), D(3), D(4), D(5)], TODAY) == 2


def test_active_yesterday_but_not_yet_today_still_counts():
    """The whole point of the yesterday anchor: at 00:01 Manila nobody has had
    a chance to contribute, and the streak must not reset on the clock."""
    assert streak_from_dates([D(1), D(2), D(3)], TODAY) == 3


def test_two_full_days_of_silence_breaks_it():
    assert streak_from_dates([D(2), D(3), D(4)], TODAY) == 0


def test_future_dates_do_not_extend_the_streak():
    """A backdated-clock or bad row must not inflate the count."""
    assert streak_from_dates([TODAY, TODAY + timedelta(days=5)], TODAY) == 1


def test_only_the_current_run_counts_not_the_longest():
    assert streak_from_dates([D(0), D(5), D(6), D(7), D(8)], TODAY) == 1


def test_order_and_duplicates_do_not_matter():
    assert streak_from_dates([D(2), D(0), D(1), D(1), D(2)], TODAY) == 3


# Manila boundary ------------------------------------------------------------

@pytest.mark.parametrize("utc_moment,expected", [
    # 23:30 UTC on the 2nd is already 07:30 Manila on the 3rd.
    (datetime(2026, 8, 2, 23, 30, tzinfo=UTC), date(2026, 8, 3)),
    # 15:59 UTC on the 3rd is 23:59 Manila on the same date - still the 3rd.
    (datetime(2026, 8, 3, 15, 59, tzinfo=UTC), date(2026, 8, 3)),
    # 16:00 UTC on the 3rd is 00:00 Manila on the 4th - the day has turned.
    (datetime(2026, 8, 3, 16, 0, tzinfo=UTC), date(2026, 8, 4)),
    # Midnight UTC is still the previous evening's date? No - 08:00 Manila.
    (datetime(2026, 8, 4, 0, 0, tzinfo=UTC), date(2026, 8, 4)),
])
def test_the_local_date_is_manila_not_utc(utc_moment, expected):
    assert today_in_manila(utc_moment) == expected


def test_manila_has_no_daylight_saving_shift():
    """Philippine time is a flat UTC+8, so a January and a July instant at the
    same UTC clock time must land on the same local date."""
    jan = today_in_manila(datetime(2026, 1, 15, 16, 0, tzinfo=UTC))
    jul = today_in_manila(datetime(2026, 7, 15, 16, 0, tzinfo=UTC))
    assert (jan.day, jul.day) == (16, 16)


# The calendar ---------------------------------------------------------------

def test_the_calendar_covers_the_whole_month():
    cells = contribution_calendar([], date(2026, 8, 27), date(2026, 8, 27))
    assert len(cells) == 31
    assert cells[0].day == date(2026, 8, 1)
    assert cells[-1].day == date(2026, 8, 31)


def test_february_length_is_not_assumed():
    assert len(contribution_calendar([], date(2026, 2, 10), date(2026, 2, 10))) == 28
    assert len(contribution_calendar([], date(2028, 2, 10), date(2028, 2, 10))) == 29


def test_only_real_contribution_dates_are_filled():
    active = {date(2026, 8, 3), date(2026, 8, 4)}
    cells = contribution_calendar(active, date(2026, 8, 27), date(2026, 8, 27))
    filled = {c.day for c in cells if c.contributed}
    assert filled == active


def test_future_days_are_never_filled():
    """The grid keeps the month's shape, but tomorrow cannot be an active day."""
    active = {date(2026, 8, 30)}
    cells = contribution_calendar(active, date(2026, 8, 27), date(2026, 8, 27))
    assert not any(c.contributed for c in cells)


def test_the_figma_sample_is_not_hardcoded_anywhere():
    """The frame shows '6 days'. Nothing may produce that without real dates."""
    assert streak_from_dates([], TODAY) == 0
    assert streak_from_dates([D(0)], TODAY) == 1


# The endpoint ---------------------------------------------------------------

from tests.conftest import register_and_token, requires_db  # noqa: E402

ENDPOINT = "/api/v1/users/me/streak"


@requires_db
def test_anonymous_is_denied(client):
    assert client.get(ENDPOINT).status_code in (401, 403)


@requires_db
def test_a_new_reviewer_has_a_zero_streak_not_an_error(client):
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_streak"] == 0
    assert body["last_contribution"] is None
    assert body["active_today"] is False
    assert body["total_days"] == 0


@requires_db
def test_the_calendar_is_returned_for_the_current_month(client):
    """Exercises the real UNION and the Postgres timezone cast — the part that
    cannot be covered by the pure tests above."""
    _, token, _ = register_and_token(client, role="user")
    body = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"}).json()
    assert 28 <= len(body["calendar"]) <= 31
    assert all(c["contributed"] is False for c in body["calendar"])
    assert body["calendar"][0]["day"].endswith("-01")


@requires_db
def test_there_is_no_way_to_ask_for_someone_elses_streak(client):
    _, token, _ = register_and_token(client, role="user")
    other = "00000000-0000-0000-0000-0000000000aa"
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/users/{other}/streak", headers=headers).status_code == 404
    body = client.get(f"{ENDPOINT}?user_id={other}", headers=headers).json()
    assert body["total_days"] == 0, "a query parameter selected another user's streak"


@requires_db
def test_the_response_carries_no_identity(client):
    _, token, _ = register_and_token(client, role="user")
    raw = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"}).text.lower()
    for forbidden in ("email", "password", "ip_address", "session", "user_id"):
        assert forbidden not in raw, f"{forbidden} leaked into the streak response"
