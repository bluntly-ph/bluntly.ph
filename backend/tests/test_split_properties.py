"""The commission split, checked as properties rather than examples.

Three things must hold for every amount and every tier, and an example-based
test will not find where they stop holding:

  1. The three shares sum to the gross exactly. No centavo appears or vanishes.
  2. No share is negative.
  3. The Honesty Fund gets exactly 30%. It is the capstone invariant, so it is
     the one that must not absorb rounding.

(2) was false. At `MAX_REVIEWER_SHARE_BPS` (7000) the reviewer takes 70% and
the fund 30%, each rounded HALF_UP independently — so when both round up they
exceed the gross by a centavo, and the platform, which absorbs the remainder,
lands at **-0.01**. It happened on 373 of 4000 random amounts.

No configured tier reaches 7000 (standard 3000, founding 3500, special 4000),
so nothing was mispaid. It is worth fixing anyway: the constant's own comment
said "above this the platform share would go negative", which reads as a
promise that at-and-below it does not.
"""

from __future__ import annotations

import random
from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.services.earnings import (
    MAX_REVIEWER_SHARE_BPS,
    split_commission,
    split_commission_tiered,
)

CENT = Decimal("0.01")

# The configured tiers, the boundaries, and the values either side of them.
TIERS = [0, 1, 3000, 3500, 4000, MAX_REVIEWER_SHARE_BPS - 1, MAX_REVIEWER_SHARE_BPS]


def amounts() -> list[Decimal]:
    """A fixed pseudo-random spread plus the awkward small values."""
    rng = random.Random(7)
    values = [Decimal(str(round(rng.uniform(0.01, 100_000), 2))) for _ in range(2000)]
    # Small amounts are where rounding decides everything.
    values += [Decimal(x) for x in
               ("0", "0.01", "0.02", "0.03", "0.04", "0.05", "0.07", "0.09",
                "0.99", "1.00", "1.01", "9.99")]
    return values


AMOUNTS = amounts()


def _shares(split: dict) -> list[Decimal]:
    return [split["platform_share"], split["reviewer_share"],
            split["honesty_fund_share"]]


@pytest.mark.parametrize("bps", TIERS)
def test_the_three_shares_sum_to_the_gross(bps):
    for gross in AMOUNTS:
        split = split_commission_tiered(gross, bps)
        assert sum(_shares(split)) == split["gross_amount"], (
            f"bps={bps} gross={gross} split={split}")


@pytest.mark.parametrize("bps", TIERS)
def test_no_share_is_ever_negative(bps):
    """The defect. At 7000 bps the platform used to land at -0.01."""
    for gross in AMOUNTS:
        split = split_commission_tiered(gross, bps)
        negative = {k: v for k, v in split.items() if v < 0}
        assert not negative, f"bps={bps} gross={gross} negative={negative}"


@pytest.mark.parametrize("bps", TIERS)
def test_the_honesty_fund_always_gets_exactly_thirty_percent(bps):
    """The fund is the fixed invariant, so it never absorbs the rounding."""
    for gross in AMOUNTS:
        split = split_commission_tiered(gross, bps)
        expected = (split["gross_amount"] * Decimal("0.30")).quantize(
            CENT, rounding=ROUND_HALF_UP)
        assert split["honesty_fund_share"] == expected, f"bps={bps} gross={gross}"


def test_the_reviewer_absorbs_the_centavo_not_the_fund():
    """Where the shortfall lands is a decision, so it gets a test.

    65093.45 at 7000 bps is one of the amounts where both shares round up.
    """
    split = split_commission_tiered(Decimal("65093.45"), MAX_REVIEWER_SHARE_BPS)
    assert split["platform_share"] == Decimal("0.00")
    assert split["honesty_fund_share"] == Decimal("19528.04")  # untouched 30%
    assert sum(_shares(split)) == split["gross_amount"]


def test_over_the_cap_is_refused():
    with pytest.raises(ValueError):
        split_commission_tiered(Decimal("100"), MAX_REVIEWER_SHARE_BPS + 1)
    with pytest.raises(ValueError):
        split_commission_tiered(Decimal("100"), -1)


class TestTheFlatSplit:
    """40/30/30 has 30% of headroom, so it cannot hit the same edge."""

    def test_sums_and_stays_positive(self):
        for gross in AMOUNTS:
            split = split_commission(gross)
            assert sum(_shares(split)) == split["gross_amount"]
            assert all(v >= 0 for v in _shares(split)), f"gross={gross}"

    def test_the_fund_gets_thirty_percent(self):
        for gross in AMOUNTS:
            split = split_commission(gross)
            expected = (split["gross_amount"] * Decimal("0.30")).quantize(
                CENT, rounding=ROUND_HALF_UP)
            assert split["honesty_fund_share"] == expected


class TestTheTierConfigCannotExceedWhatTheSplitAccepts:
    """Two bounds on one number, in two files, with nothing keeping them equal.

    `TierUpdate.revenue_share_bps` was capped at 10000 — a round number, not the
    domain's. `MAX_REVIEWER_SHARE_BPS` is 7000, above which
    `split_commission_tiered` raises. A moderator could therefore save a tier at
    8000, and nothing would fail until the next commission import for that tier,
    which would throw a ValueError mid-batch some time later.
    """

    def test_the_schema_bound_is_the_domain_bound(self):
        from app.schemas.membership import TierUpdate
        field = TierUpdate.model_fields["revenue_share_bps"]
        ceiling = next((getattr(m, "le", None) for m in field.metadata
                        if getattr(m, "le", None) is not None), None)
        assert ceiling == MAX_REVIEWER_SHARE_BPS, (
            f"TierUpdate allows {ceiling} but the split accepts at most "
            f"{MAX_REVIEWER_SHARE_BPS}; a tier saved above that throws on every "
            f"commission for it")

    @pytest.mark.parametrize("bps", [0, 3000, 3500, 4000, MAX_REVIEWER_SHARE_BPS])
    def test_anything_the_schema_accepts_the_split_accepts(self, bps):
        from app.schemas.membership import TierUpdate
        assert TierUpdate(revenue_share_bps=bps).revenue_share_bps == bps
        split_commission_tiered(Decimal("1234.56"), bps)  # must not raise

    def test_the_schema_refuses_what_the_split_would_reject(self):
        from pydantic import ValidationError

        from app.schemas.membership import TierUpdate
        for bad in (MAX_REVIEWER_SHARE_BPS + 1, 10000):
            with pytest.raises(ValidationError):
                TierUpdate(revenue_share_bps=bad)
