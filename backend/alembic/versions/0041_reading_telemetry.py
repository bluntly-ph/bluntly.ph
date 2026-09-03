"""reading telemetry: one row per review impression, plus first-vote geography

COLLECTION ONLY. Nothing in either table is read by code that computes a score,
a rank, a moderator priority, a publication decision, a vote weight, a fund
share, or a payout. See docs/superpowers/specs/2026-09-03-review-integrity-
telemetry-phase-1-design.md and tests/test_telemetry_isolation.py.

IDENTITY. Two columns, exactly one non-null, enforced by CHECK rather than by
convention. A signed-in reader's row carries `reader_ref` and no pseudonym; a
signed-out reader's row carries `anon_ref` and no account. They therefore cannot
be joined inside the database, which is the property that makes a rotating
pseudonym meaningfully different from a durable one. `reader_ref` cascades, so
deleting an account erases its reading history with no bespoke code.

WHY NOT ONE POLYMORPHIC COLUMN. It could carry neither the foreign key nor the
cascade, and every future query against it would be ambiguous about what it was
joining.

GEOGRAPHY. `country` only on the impression row. City beside a reader pseudonym
is a coarse location trail; city-level analysis stays in request_geo_buckets,
which carries no identity at all (0032).

Additive: one enum type, two tables, no change to any existing object.

Revision ID: 0041_reading_telemetry
Revises: 0040_role_admin_audit_enum
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0041_reading_telemetry"
down_revision = "0040_role_admin_audit_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration creates the type explicitly; the table column must not
    # emit a second CREATE TYPE through SQLAlchemy's native-enum DDL hook.
    reader_kind = postgresql.ENUM("anon", "user", name="reader_kind", create_type=False)
    reader_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "review_reading_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("impression_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "review_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reader_kind", reader_kind, nullable=False),
        sa.Column(
            "reader_ref",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("anon_ref", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("active_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("body_active_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wall_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scroll_milestone", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("checkpoints", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("max_seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clamped", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vote_client_after_ms", sa.Integer, nullable=True),
        sa.Column("report_client_after_ms", sa.Integer, nullable=True),
        sa.Column("comment_client_after_ms", sa.Integer, nullable=True),
        sa.Column("share_client_after_ms", sa.Integer, nullable=True),
        sa.Column("photo_client_after_ms", sa.Integer, nullable=True),
        sa.Column("outlink_client_after_ms", sa.Integer, nullable=True),
        sa.Column("first_vote_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_ms_at_first_vote", sa.Integer, nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("word_count_at_view", sa.SmallInteger, nullable=True),
        sa.Column("star_rating_at_view", sa.SmallInteger, nullable=True),
        sa.Column("device_class", sa.SmallInteger, nullable=False, server_default="0"),
        sa.CheckConstraint(
            "(reader_kind = 'user') = (reader_ref IS NOT NULL)", name="ck_reading_reader_user"
        ),
        sa.CheckConstraint(
            "(reader_kind = 'anon') = (anon_ref IS NOT NULL)", name="ck_reading_reader_anon"
        ),
        sa.CheckConstraint("scroll_milestone IN (0,25,50,75,100)", name="ck_reading_scroll"),
        sa.CheckConstraint("device_class BETWEEN 0 AND 3", name="ck_reading_device"),
        sa.CheckConstraint(
            "active_ms >= 0 AND body_active_ms >= 0 AND wall_ms >= 0", name="ck_reading_ms_signs"
        ),
        sa.CheckConstraint("body_active_ms <= active_ms", name="ck_reading_body_le_act"),
        sa.CheckConstraint(
            "active_ms <= 1800000 AND body_active_ms <= 1800000 AND wall_ms <= 1800000",
            name="ck_reading_duration_cap",
        ),
        sa.CheckConstraint(
            "checkpoints BETWEEN 1 AND 16 AND max_seq >= 0", name="ck_reading_checkpoint_cap"
        ),
        sa.CheckConstraint(
            "(vote_client_after_ms IS NULL OR vote_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(report_client_after_ms IS NULL OR report_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(comment_client_after_ms IS NULL OR comment_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(share_client_after_ms IS NULL OR share_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(photo_client_after_ms IS NULL OR photo_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(outlink_client_after_ms IS NULL OR outlink_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(active_ms_at_first_vote IS NULL OR active_ms_at_first_vote BETWEEN 0 AND 1800000)",
            name="ck_reading_interaction_cap",
        ),
    )
    # The UPSERT target AND the replay fence: one impression, one row, forever.
    op.create_index("uq_reading_impression", "review_reading_sessions", ["impression_id"], unique=True)
    # Retention is one indexed range scan over this column.
    op.create_index("ix_reading_started_at", "review_reading_sessions", ["started_at"])
    # The analytical read: "this review's impressions over a window".
    op.create_index("ix_reading_review_started", "review_reading_sessions", ["review_id", "started_at"])
    # Vote-timing join. Partial, so anon rows cost nothing to maintain.
    op.create_index(
        "ix_reading_reader_review",
        "review_reading_sessions",
        ["reader_ref", "review_id"],
        postgresql_where=sa.text("reader_ref IS NOT NULL"),
    )

    op.create_table(
        "review_first_vote_geo_buckets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "review_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("first_vote_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # NULLS NOT DISTINCT matters exactly as it did in 0032: three of these
    # columns are nullable, and under the default two country-only rows for the
    # same hour would never conflict, so every vote would INSERT and the
    # "aggregate" would grow like a log.
    op.execute(
        "CREATE UNIQUE INDEX uq_review_first_vote_geo "
        "ON review_first_vote_geo_buckets "
        "(review_id, bucket_start, country, region, city) NULLS NOT DISTINCT"
    )
    op.create_index("ix_review_first_vote_geo_start", "review_first_vote_geo_buckets", ["bucket_start"])


def downgrade() -> None:
    op.drop_index("ix_review_first_vote_geo_start", table_name="review_first_vote_geo_buckets")
    op.drop_index("uq_review_first_vote_geo", table_name="review_first_vote_geo_buckets")
    op.drop_table("review_first_vote_geo_buckets")
    op.drop_index("ix_reading_reader_review", table_name="review_reading_sessions")
    op.drop_index("ix_reading_review_started", table_name="review_reading_sessions")
    op.drop_index("ix_reading_started_at", table_name="review_reading_sessions")
    op.drop_index("uq_reading_impression", table_name="review_reading_sessions")
    op.drop_table("review_reading_sessions")
    sa.Enum(name="reader_kind").drop(op.get_bind(), checkfirst=True)
