"""report resolution — a filed report can now be closed (owner §30, 2026-09-16)

`moderation_logs` rows with `action='report'` are the community report queue.
Nothing could close one: the queue read every report ever filed, forever, so a
moderator who acted on a report had no way to say so and the next moderator saw
the same row again. "Inspection only" is no longer acceptable for moderation, so
a report needs an outcome.

Three nullable columns on `moderation_logs`, meaningful only for report rows:

    resolution   what the moderator decided (native enum `report_resolution`)
    resolved_at  when
    resolved_by  who — SET NULL on account deletion, like every other actor
                 reference in this table

Not a separate table: a report IS a moderation_logs row, and its outcome belongs
on it. The action the moderator took (unpublishing, restoring, escalating) is
still written as its own audit row by the services that perform it — this only
records that THIS report has been dealt with, and how.

A partial index serves the queue's one hot read, "reports still open".

Revision ID: 0049_report_resolution
Revises: 0048_half_star_ratings
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0049_report_resolution"
down_revision = "0048_half_star_ratings"
branch_labels = None
depends_on = None

RESOLUTIONS = ("dismissed", "content_removed", "content_restored", "escalated")


def upgrade() -> None:
    resolution = sa.Enum(*RESOLUTIONS, name="report_resolution")
    resolution.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "moderation_logs",
        sa.Column("resolution", resolution, nullable=True),
    )
    op.add_column(
        "moderation_logs",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "moderation_logs",
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_moderation_logs_resolved_by",
        "moderation_logs",
        "users",
        ["resolved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    # The queue's only hot read: open reports, newest first.
    op.create_index(
        "ix_moderation_logs_open_reports",
        "moderation_logs",
        ["created_at"],
        postgresql_where=sa.text("action = 'report' AND resolution IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_moderation_logs_open_reports", table_name="moderation_logs")
    op.drop_constraint("fk_moderation_logs_resolved_by", "moderation_logs",
                       type_="foreignkey")
    op.drop_column("moderation_logs", "resolved_by")
    op.drop_column("moderation_logs", "resolved_at")
    op.drop_column("moderation_logs", "resolution")
    sa.Enum(name="report_resolution").drop(op.get_bind(), checkfirst=True)
