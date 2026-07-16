"""align the migrated schema with the ORM models (M3 verification)

`alembic check` caught real drift: migrations 0009–0013 built columns NULLABLE
that the models declare NOT NULL, and used UNIQUE CONSTRAINT + a plain index
where the models (`unique=True, index=True`) declare a UNIQUE INDEX.

Why it matters, concretely: `review_contracts.auto_renew` NULL is falsy, so a
NULL row would silently **expire** instead of renewing — a contract quietly
ending is real money. Nothing writes NULL today (the services always set these),
so this is a latent gap being closed, not a live bug. Backfills defensively
before tightening so it is safe on any existing data.

Revision ID: 0014_schema_parity
Revises: 0013_referral_sub_id
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_schema_parity"
down_revision = "0013_referral_sub_id"
branch_labels = None
depends_on = None

# (table, column, server_default used for the backfill, type)
_NOT_NULL = [
    ("payouts", "currency", "'PHP'", sa.String(length=3)),
    ("referral_links", "sub_id_in_url", "false", sa.Boolean()),
    ("review_contracts", "auto_renew", "true", sa.Boolean()),
    ("review_contracts", "renewal_count", "0", sa.Integer()),
    ("review_requests", "upvote_count", "0", sa.Integer()),
]

# (table, column, plain index name, unique constraint name)
_UNIQUE_INDEXES = [
    ("payouts", "payout_id", "ix_payouts_payout_id", "payouts_payout_id_key"),
    ("review_requests", "request_id", "ix_review_requests_request_id",
     "review_requests_request_id_key"),
]


def upgrade() -> None:
    for table, column, default, coltype in _NOT_NULL:
        op.execute(f"UPDATE {table} SET {column} = {default} WHERE {column} IS NULL")
        op.alter_column(table, column, existing_type=coltype, nullable=False)

    # The models declare `unique=True, index=True` -> ONE unique index. The
    # migrations produced a unique constraint plus a separate plain index.
    for table, column, index_name, constraint_name in _UNIQUE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name}")
        op.execute(f"CREATE UNIQUE INDEX {index_name} ON {table} ({column})")


def downgrade() -> None:
    for table, column, index_name, constraint_name in _UNIQUE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
                   f"UNIQUE ({column})")
        op.execute(f"CREATE INDEX {index_name} ON {table} ({column})")
    for table, column, _default, coltype in _NOT_NULL:
        op.alter_column(table, column, existing_type=coltype, nullable=True)
