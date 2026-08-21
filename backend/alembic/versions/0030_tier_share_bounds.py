"""bound membership_tiers.revenue_share_bps at the database

`TierUpdate` was capped at 10000 while `split_commission_tiered` raises above
`MAX_REVIEWER_SHARE_BPS` (7000) — the Honesty Fund's fixed 30% leaves the
platform negative beyond that. The schema now imports the constant, so the API
cannot save an unusable tier, but the API is not the only writer:
`reset_and_seed.py`, `seed.py` and any admin SQL write this column directly.

A tier saved above the cap does not fail when it is saved. It fails later,
mid-batch, as an unhandled ValueError on the next commission import for that
tier — far from the change that caused it and looking nothing like it.

**Verified against production before writing.** The three configured tiers are
special 4000, founding 3500, standard 3000, so every row already conforms with
a wide margin, and adding a satisfied CHECK rewrites nothing and cannot break
deployed code. Safe in either deploy order.

The lower bound is 0 rather than 1: a tier that pays the reviewer nothing is a
strange product decision but a coherent one, and the split handles it.

Revision ID: 0030_tier_share_bounds
Revises: 0029_revoke_postgrest_access
"""
from __future__ import annotations

from alembic import op

revision = "0030_tier_share_bounds"
down_revision = "0029_revoke_postgrest_access"
branch_labels = None
depends_on = None

# Kept as a literal rather than imported from app.services.earnings: a
# migration records what the database was told at the time it ran, and must not
# change meaning later because a constant moved. The test in
# tests/test_split_properties.py is what keeps the two equal going forward.
MAX_REVIEWER_SHARE_BPS = 7000


def upgrade() -> None:
    op.execute(
        "ALTER TABLE membership_tiers ADD CONSTRAINT ck_tier_share_bps_range "
        f"CHECK (revenue_share_bps BETWEEN 0 AND {MAX_REVIEWER_SHARE_BPS})")
    # payout_priority orders who is paid first when a batch runs. Negative would
    # not crash anything; it would quietly jump a tier to the front of the queue.
    op.execute(
        "ALTER TABLE membership_tiers ADD CONSTRAINT ck_tier_payout_priority "
        "CHECK (payout_priority >= 0)")


def downgrade() -> None:
    op.execute("ALTER TABLE membership_tiers "
               "DROP CONSTRAINT IF EXISTS ck_tier_payout_priority")
    op.execute("ALTER TABLE membership_tiers "
               "DROP CONSTRAINT IF EXISTS ck_tier_share_bps_range")
