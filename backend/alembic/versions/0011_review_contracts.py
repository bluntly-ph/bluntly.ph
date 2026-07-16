"""review_contracts + commissions.contract_status snapshot (M3 slice 10)

- review_contracts with a partial unique index: one ACTIVE contract per review.
- commissions.contract_status: the contract state snapshotted at reconciliation,
  so a commission row explains its own reviewer share forever (same immutable-
  audit principle as reviewer_tier/reviewer_share_bps in 0008).

Revision ID: 0011_review_contracts
Revises: 0010_request_board
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_review_contracts"
down_revision = "0010_request_board"
branch_labels = None
depends_on = None

contract_status = postgresql.ENUM(
    "active", "expired", "bought_out", name="contract_status", create_type=False
)


def upgrade() -> None:
    contract_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "review_contracts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("status", contract_status, server_default="active", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), server_default="true", nullable=True),
        sa.Column("renewal_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("buyout_offer_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("buyout_offered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("buyout_offered_by", sa.UUID(), nullable=True),
        sa.Column("buyout_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("buyout_rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["buyout_offered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_contracts_review_id", "review_contracts", ["review_id"])
    op.create_index("ix_review_contracts_expires_at", "review_contracts", ["expires_at"])
    # Exactly one active contract per review.
    op.execute("CREATE UNIQUE INDEX uq_contract_active ON review_contracts (review_id) "
               "WHERE status = 'active'")

    op.add_column("commissions", sa.Column("contract_status", contract_status, nullable=True))

    op.execute("ALTER TABLE review_contracts ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY review_contracts_select_public ON review_contracts "
               "FOR SELECT USING (true)")


def downgrade() -> None:
    op.drop_column("commissions", "contract_status")
    op.execute("DROP POLICY IF EXISTS review_contracts_select_public ON review_contracts")
    op.execute("DROP INDEX IF EXISTS uq_contract_active")
    op.drop_index("ix_review_contracts_expires_at", table_name="review_contracts")
    op.drop_index("ix_review_contracts_review_id", table_name="review_contracts")
    op.drop_table("review_contracts")
    contract_status.drop(op.get_bind(), checkfirst=True)
