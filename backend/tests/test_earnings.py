"""Commission split arithmetic + Honesty Fund multiplier tests (FR-6)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.earnings import split_commission
from app.services.trust import honesty_score


@pytest.mark.parametrize("gross", ["100.00", "0.01", "99.99", "12345.67", "3.33", "1000000.00"])
def test_split_sums_to_gross(gross):
    parts = split_commission(Decimal(gross))
    total = parts["platform_share"] + parts["reviewer_share"] + parts["honesty_fund_share"]
    assert total == Decimal(gross)


def test_split_ratios_are_40_30_30_on_clean_amount():
    parts = split_commission(Decimal("100.00"))
    assert parts["platform_share"] == Decimal("40.00")
    assert parts["reviewer_share"] == Decimal("30.00")
    assert parts["honesty_fund_share"] == Decimal("30.00")


def test_split_is_deterministic_idempotent():
    # Re-splitting the same gross yields identical shares (supports idempotent import).
    a = split_commission(Decimal("777.77"))
    b = split_commission(Decimal("777.77"))
    assert a == b


def test_honesty_price_brackets():
    votes = Decimal("10")
    assert honesty_score(votes, Decimal("499")) == Decimal("10.0")     # 1.0x
    assert honesty_score(votes, Decimal("500")) == Decimal("15.0")     # 1.5x
    assert honesty_score(votes, Decimal("1499")) == Decimal("15.0")    # 1.5x
    assert honesty_score(votes, Decimal("1500")) == Decimal("20.0")    # 2.0x
