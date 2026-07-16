"""request board — review_requests + request_upvotes (M3 slice 9)

- token_kind enum += spend_request_escrow / earn_request_reward /
  refund_request_escrow / platform_topup (ADD VALUE -> autocommit block).
- new request_status enum.
- RLS on both tables with a public SELECT policy (the board is public).

Revision ID: 0010_request_board
Revises: 0009_tokens
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_request_board"
down_revision = "0009_tokens"
branch_labels = None
depends_on = None

request_status = postgresql.ENUM(
    "open", "fulfilled", "cancelled", "expired", "removed",
    name="request_status", create_type=False,
)

_NEW_TOKEN_KINDS = (
    "spend_request_escrow", "earn_request_reward",
    "refund_request_escrow", "platform_topup",
)


def upgrade() -> None:
    # 1. Enum ADD VALUE must run outside the migration transaction.
    with op.get_context().autocommit_block():
        for value in _NEW_TOKEN_KINDS:
            op.execute(f"ALTER TYPE token_kind ADD VALUE IF NOT EXISTS '{value}'")

    request_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "review_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("request_id", sa.String(length=32), nullable=True),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("bounty", sa.Integer(), nullable=False),
        sa.Column("status", request_status, server_default="open", nullable=False),
        sa.Column("fulfilled_by_review_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upvote_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("ai_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fulfilled_by_review_id"], ["reviews.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_review_requests_request_id", "review_requests", ["request_id"])
    op.create_index("ix_review_requests_status", "review_requests", ["status"])
    op.create_index("ix_review_requests_expires_at", "review_requests", ["expires_at"])

    op.create_table(
        "request_upvotes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["review_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "user_id", name="uq_request_upvote_once"),
    )
    op.create_index("ix_request_upvotes_request_id", "request_upvotes", ["request_id"])

    for table in ("review_requests", "request_upvotes"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_select_public ON {table} "
                   "FOR SELECT USING (true)")


def downgrade() -> None:
    for table in ("request_upvotes", "review_requests"):
        op.execute(f"DROP POLICY IF EXISTS {table}_select_public ON {table}")
    op.drop_index("ix_request_upvotes_request_id", table_name="request_upvotes")
    op.drop_table("request_upvotes")
    for idx in ("ix_review_requests_expires_at", "ix_review_requests_status",
                "ix_review_requests_request_id"):
        op.drop_index(idx, table_name="review_requests")
    op.drop_table("review_requests")
    request_status.drop(op.get_bind(), checkfirst=True)
    # Postgres cannot DROP enum values, so the new token_kind values remain
    # (harmless — consistent with 0004's documented behaviour).
