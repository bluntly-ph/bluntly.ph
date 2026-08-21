"""Global business constants.

These replace values the source spec stored redundantly per-row (e.g. the
per-user `share_percentage` TEXT column — see the deviations changelog). Keeping
them as single constants removes the drift risk flagged in Architecture §4.
"""

from __future__ import annotations

from decimal import Decimal

# --- Revenue split (FR-6). ---
#
# 40/30/30 is the BASELINE, not what every commission does. The live path is
# `split_commission_tiered`, which takes the reviewer's share from
# `membership_tiers.revenue_share_bps` — 3000 for standard, which reproduces
# 40/30/30 exactly, and 3500 or 4000 for founding and special.
#
# What stays fixed across all of them is the Honesty Fund's 30%: a tier upgrade
# comes out of the platform's share and never the fund's. That is the capstone
# invariant, and it is why the platform absorbs the rounding remainder rather
# than the fund.
PLATFORM_SHARE = Decimal("0.40")
REVIEWER_SHARE = Decimal("0.30")
HONESTY_FUND_SHARE = Decimal("0.30")

# --- Payouts (FR-6). ---
PAYOUT_MINIMUM_PHP = Decimal("300.00")
PAYOUT_CURRENCY = "PHP"

# --- Honesty Fund price-bracket multipliers (FR-6). ---
def honesty_price_multiplier(price_php: Decimal) -> Decimal:
    """1.0x below 500; 1.5x 500–1,499; 2.0x 1,500+."""
    if price_php >= Decimal("1500"):
        return Decimal("2.0")
    if price_php >= Decimal("500"):
        return Decimal("1.5")
    return Decimal("1.0")

# --- Seeding → Post-Seeding transition threshold (PRD §2). ---
SEEDING_TRANSITION_STAGE2_REVIEWERS = 50

# --- Account maturation (FR-7): accounts < 30 days get halved gate vote weight. ---
ACCOUNT_MATURATION_DAYS = 30

# --- PII retention schedule for `sessions` (Architecture §4). ---
SESSION_IP_HASH_AFTER_DAYS = 30
SESSION_IP_DELETE_AFTER_DAYS = 90
SESSION_UA_PURGE_AFTER_DAYS = 90
