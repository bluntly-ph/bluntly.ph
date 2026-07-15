"""pg_trgm extension + trigram index for duplicate-content detection (M2 slice 5)

Available on Supabase and in the postgres:16 image. The GIN trigram index keeps
the moderator-queue similarity probe bounded.

Revision ID: 0007_pg_trgm
Revises: 0006_trust_ratings
"""
from __future__ import annotations

from alembic import op

revision = "0007_pg_trgm"
down_revision = "0006_trust_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reviews_discussion_trgm "
               "ON reviews USING gin (discussion gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reviews_discussion_trgm")
    # The extension is left installed: other objects may depend on it and
    # dropping extensions on shared instances (Supabase) is not our call.
