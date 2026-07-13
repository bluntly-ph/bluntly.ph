"""Commission split arithmetic (FR-6, §3.3).

The 40/30/30 split must be exact to the centavo and always re-sum to the gross
(no rounding leakage). The platform share absorbs the rounding remainder.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.constants import HONESTY_FUND_SHARE, REVIEWER_SHARE

_CENT = Decimal("0.01")


def split_commission(gross: Decimal) -> dict[str, Decimal]:
    """Split `gross` 40/30/30. Reviewer & Honesty Fund are rounded to the centavo;
    the platform share takes the remainder so the three always sum to `gross`.
    """
    gross = Decimal(gross).quantize(_CENT, rounding=ROUND_HALF_UP)
    reviewer = (gross * REVIEWER_SHARE).quantize(_CENT, rounding=ROUND_HALF_UP)
    honesty = (gross * HONESTY_FUND_SHARE).quantize(_CENT, rounding=ROUND_HALF_UP)
    platform = gross - reviewer - honesty
    return {
        "gross_amount": gross,
        "platform_share": platform,
        "reviewer_share": reviewer,
        "honesty_fund_share": honesty,
    }
