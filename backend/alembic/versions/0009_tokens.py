"""token economy — balance column + append-only ledger (M2 slice 7)

- users.token_balance int NOT NULL default 0 (mirror of the ledger).
- token_transactions: append-only; balance_after chain; token_kind enum.
- uq_token_once: a given (user, earn kind, ref) awards exactly once.
- RLS enabled with NO permissive policy (backend-enforced own-rows access,
  same posture as `sessions`).

Revision ID: 0009_tokens
Revises: 0008_commission_tier_snapshot
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_tokens"
down_revision = "0008_commission_tier_snapshot"
branch_labels = None
depends_on = None

token_kind = postgresql.ENUM(
    "earn_review_published", "earn_commission", "admin_grant", "admin_deduct",
    "adjustment", name="token_kind", create_type=False,
)


def upgrade() -> None:
    token_kind.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column(
        "token_balance", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "token_transactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("kind", token_kind, nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=True),
        sa.Column("ref_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount <> 0", name="ck_token_amount_nonzero"),
    )
    op.create_index("ix_token_tx_user_created", "token_transactions",
                    ["user_id", sa.text("created_at DESC")])
    # Idempotency: one earn per (user, kind, ref). Enum literals (not a ::text
    # cast) — enum casts aren't IMMUTABLE, which index predicates require.
    op.execute(
        "CREATE UNIQUE INDEX uq_token_once ON token_transactions (user_id, kind, ref_id) "
        "WHERE ref_id IS NOT NULL "
        "AND kind IN ('earn_review_published'::token_kind, 'earn_commission'::token_kind)"
    )
    # RLS with no permissive policy: nothing is readable via anon/authenticated
    # Postgres roles; the API is the only door (like `sessions`).
    op.execute("ALTER TABLE token_transactions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_token_once")
    op.drop_index("ix_token_tx_user_created", table_name="token_transactions")
    op.drop_table("token_transactions")
    op.drop_column("users", "token_balance")
    token_kind.drop(op.get_bind(), checkfirst=True)
