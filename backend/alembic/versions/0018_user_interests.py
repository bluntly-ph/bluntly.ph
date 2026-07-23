"""users.interests — onboarding category picks (Slice 1 Phase A)

Onboarding step 2 asks the user to pick interests to seed their feed. Stored as
a JSONB array of category slugs rather than a join table: products.category is
itself a free String(120), so there is no category entity to foreign-key to, and
the list is read whole or not at all.

Revision ID: 0018_user_interests
Revises: 0017_avatar
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018_user_interests"
down_revision = "0017_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("interests", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "interests")
