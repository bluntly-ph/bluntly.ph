"""payouts — earnings disbursement (M3 slice 11)

RLS enabled with NO permissive policy (financial data; same posture as
`sessions` and `token_transactions`).

Revision ID: 0012_payouts
Revises: 0011_review_contracts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_payouts"
down_revision = "0011_review_contracts"
branch_labels = None
depends_on = None

payout_status = postgresql.ENUM(
    "scheduled", "processing", "paid", "failed", "cancelled",
    name="payout_status", create_type=False,
)
payout_method = postgresql.ENUM(
    "paypal_sandbox", "paypal_live", "manual", name="payout_method", create_type=False
)


def upgrade() -> None:
    payout_status.create(op.get_bind(), checkfirst=True)
    payout_method.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "payouts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payout_id", sa.String(length=48), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="PHP", nullable=True),
        sa.Column("status", payout_status, server_default="scheduled", nullable=False),
        sa.Column("method", payout_method, nullable=False),
        sa.Column("provider_ref", sa.String(length=128), nullable=True),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_id"),
    )
    op.create_index("ix_payouts_payout_id", "payouts", ["payout_id"])
    op.create_index("ix_payouts_user_id", "payouts", ["user_id"])
    op.create_index("ix_payouts_status", "payouts", ["status"])
    op.create_index("ix_payouts_batch_id", "payouts", ["batch_id"])
    # One in-flight payout per user per batch — a scheduler re-run cannot
    # double-schedule the same person for the same cycle.
    op.execute("CREATE UNIQUE INDEX uq_payout_user_batch ON payouts (user_id, batch_id) "
               "WHERE batch_id IS NOT NULL")
    op.execute("ALTER TABLE payouts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_payout_user_batch")
    for idx in ("ix_payouts_batch_id", "ix_payouts_status", "ix_payouts_user_id",
                "ix_payouts_payout_id"):
        op.drop_index(idx, table_name="payouts")
    op.drop_table("payouts")
    payout_method.drop(op.get_bind(), checkfirst=True)
    payout_status.drop(op.get_bind(), checkfirst=True)
