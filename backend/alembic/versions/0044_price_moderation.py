"""price observation moderation and provenance (FR-2)

The completion contract makes every price observation pending, approved or
rejected, and the price panel is built from approved observations only. It also
requires the composer's "Let's talk money" price to feed the same pipeline, so
an observation records where it came from and, for a review, which one.

**Existing rows become pending, not approved.** Every observation already in
`price_history` was counted without anyone checking it. Marking them approved
would record a moderation decision nobody made, so they take the column default
and wait in the moderator queue. The visible effect is that a product whose
panel was open closes until a moderator approves its prices. That is the rule
the contract states, applied to old data as well as new.

One observation per review at most (a partial unique index), so resubmitting or
editing a review cannot multiply the price it reported.

Additive: two enum types, defaulted or nullable columns, two indexes. Safe to
apply before the code that reads them is deployed — the old code ignores the
new columns, and the default keeps what it writes pending.

Revision ID: 0044_price_moderation
Revises: 0043_seller_review_content
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0044_price_moderation"
down_revision = "0043_seller_review_content"
branch_labels = None
depends_on = None

STATUS = "price_observation_status"
SOURCE = "price_observation_source"


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("pending", "approved", "rejected", name=STATUS).create(bind, checkfirst=True)
    postgresql.ENUM("manual", "review", name=SOURCE).create(bind, checkfirst=True)
    # Bound with create_type=False: the types exist now, and an ENUM that still
    # thinks it owns its type emits CREATE TYPE again (see 0042).
    status = postgresql.ENUM(name=STATUS, create_type=False)
    source = postgresql.ENUM(name=SOURCE, create_type=False)

    op.add_column("price_history", sa.Column(
        "status", status, nullable=False, server_default="pending"))
    op.add_column("price_history", sa.Column(
        "source", source, nullable=False, server_default="manual"))
    op.add_column("price_history", sa.Column(
        "review_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("reviews.id", ondelete="SET NULL")))
    op.add_column("price_history", sa.Column(
        "decided_by_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("price_history", sa.Column("decided_at", sa.DateTime(timezone=True)))
    op.add_column("price_history", sa.Column("decision_note", sa.Text()))

    op.create_index("ix_price_history_product_status", "price_history",
                    ["product_id", "status"])
    op.create_index("uq_price_history_review", "price_history", ["review_id"],
                    unique=True, postgresql_where=sa.text("review_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_price_history_review", table_name="price_history")
    op.drop_index("ix_price_history_product_status", table_name="price_history")
    for column in ("decision_note", "decided_at", "decided_by_id", "review_id",
                   "source", "status"):
        op.drop_column("price_history", column)
    bind = op.get_bind()
    postgresql.ENUM(name=SOURCE).drop(bind, checkfirst=True)
    postgresql.ENUM(name=STATUS).drop(bind, checkfirst=True)
