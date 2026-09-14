"""in-app notifications (FR-1 1.6)

One table: a row per event on one account's own content, written in the same
transaction as the event. Two indexes: the list (account, newest first) and a
partial index over unread rows for the badge count every signed-in page asks
for.

Additive: a new table only.

Revision ID: 0047_notifications
Revises: 0046_review_disclosure
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0047_notifications"
down_revision = "0046_review_disclosure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("link", sa.String(300)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_unread", "notifications", ["user_id"],
                    postgresql_where=sa.text("read_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
