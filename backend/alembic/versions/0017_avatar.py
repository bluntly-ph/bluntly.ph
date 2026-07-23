"""users.avatar_url — profile image in Supabase Storage (Slice 1 Phase A)

Stores the public URL rather than the object path so the column is directly
renderable; `services/storage.py` parses the path back out when replacing or
deleting an object.

Revision ID: 0017_avatar
Revises: 0016_username
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_avatar"
down_revision = "0016_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
