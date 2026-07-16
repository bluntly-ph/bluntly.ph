"""referral_links.sub_id — affiliate attribution key (M3 slice 12)

The real Shopee/Lazada exports carry NO click_ref: the only field that survives
the round trip to the marketplace and back into the report is the affiliate
sub-ID, which the moderator sets when generating the link (Shopee `Sub_id1..5`,
Lazada `Aff Sub ID` / `Sub ID 1..6`). Without it, report rows cannot be
attributed to a reviewer. Backfilled deterministically for existing links so
historical rows are matchable if their reports ever carry one.

Revision ID: 0013_referral_sub_id
Revises: 0012_payouts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_referral_sub_id"
down_revision = "0012_payouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("referral_links", sa.Column("sub_id", sa.String(length=64), nullable=True))
    op.add_column("referral_links", sa.Column(
        "sub_id_in_url", sa.Boolean(), server_default="false", nullable=True))
    # Deterministic backfill: same rule as the service (blt_<12 hex of review id>),
    # so an existing link's sub-ID is reproducible rather than random.
    op.execute("UPDATE referral_links SET sub_id = 'blt_' || substr(replace("
               "review_id::text, '-', ''), 1, 12) WHERE sub_id IS NULL")
    op.create_index("ix_referral_links_sub_id", "referral_links", ["sub_id"])
    # Unique among ACTIVE links only. A sub-ID identifies the REVIEW, and a review
    # legitimately has several links over time (revoke -> re-attach); those share
    # the review's sub-ID and all attribute to the same review, so a plain unique
    # index would wrongly reject a re-attach. What must never happen is two
    # *live* links answering to one sub-ID.
    op.execute("CREATE UNIQUE INDEX uq_referral_sub_id_active ON referral_links (sub_id) "
               "WHERE sub_id IS NOT NULL AND status = 'active'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_referral_sub_id_active")
    op.drop_index("ix_referral_links_sub_id", table_name="referral_links")
    op.drop_column("referral_links", "sub_id_in_url")
    op.drop_column("referral_links", "sub_id")
