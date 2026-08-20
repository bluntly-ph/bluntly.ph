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


# Above this the platform share would go negative before rounding is even
# considered (the 30% Honesty Fund is fixed). At exactly 7000 it can still
# land at -0.01 when both shares round up, which is what `platform` guards
# against below.
MAX_REVIEWER_SHARE_BPS = 7000


def split_commission_tiered(gross: Decimal, reviewer_share_bps: int) -> dict[str, Decimal]:
    """Tier-based split (M2 slice 6). Honesty Fund is a FIXED 30% (capstone
    invariant); the reviewer takes `reviewer_share_bps`/10000 (standard 3000,
    founding 3500, special 4000); the platform absorbs the rounding remainder so
    the three ALWAYS sum to `gross` to the centavo.
    """
    if not 0 <= reviewer_share_bps <= MAX_REVIEWER_SHARE_BPS:
        raise ValueError(f"reviewer_share_bps must be 0..{MAX_REVIEWER_SHARE_BPS}")
    gross = Decimal(gross).quantize(_CENT, rounding=ROUND_HALF_UP)
    reviewer = (gross * Decimal(reviewer_share_bps) / Decimal(10000)).quantize(
        _CENT, rounding=ROUND_HALF_UP)
    honesty = (gross * HONESTY_FUND_SHARE).quantize(_CENT, rounding=ROUND_HALF_UP)
    platform = gross - reviewer - honesty

    # At 7000 bps the shares are 70% and 30%, each rounded HALF_UP
    # independently - so when both round up they exceed `gross` by a centavo and
    # the platform, which absorbs the remainder, lands at -0.01. Measured on 373
    # of 4000 random amounts. No configured tier reaches 7000 (standard 3000,
    # founding 3500, special 4000), so this is a boundary rather than a live
    # bug - but a negative share should not be representable at all, and the
    # cap's own comment implied at-and-below it was safe.
    #
    # The reviewer gives up the centavo, not the Honesty Fund: the fund's 30% is
    # the capstone invariant, and a negative platform share would mean the
    # platform paid to broker the sale.
    if platform < 0:
        reviewer += platform
        platform = Decimal("0.00")

    return {
        "gross_amount": gross,
        "platform_share": platform,
        "reviewer_share": reviewer,
        "honesty_fund_share": honesty,
    }
