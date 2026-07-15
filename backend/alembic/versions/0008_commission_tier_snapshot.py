"""commission tier snapshot columns (M2 slice 6)

reviewer_tier + reviewer_share_bps are snapshotted at reconciliation time so the
commission stays an immutable audit record even if the user's tier changes later
(same principle as gate-vote snapshots).

Revision ID: 0008_commission_tier_snapshot
Revises: 0007_pg_trgm
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_commission_tier_snapshot"
down_revision = "0007_pg_trgm"
branch_labels = None
depends_on = None

membership_tier = postgresql.ENUM(name="membership_tier", create_type=False)


def upgrade() -> None:
    op.add_column("commissions", sa.Column("reviewer_tier", membership_tier, nullable=True))
    op.add_column("commissions", sa.Column("reviewer_share_bps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("commissions", "reviewer_share_bps")
    op.drop_column("commissions", "reviewer_tier")
