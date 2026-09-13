"""seller review title, photos, and moderator removal (FR-4)

The owner's seller-review composer asks for a title ("Make it pop") and photos
alongside the prose, and 0042 had room for neither. Seller reviews also publish
without the product-review moderation gate, so a moderator needs a way to take
one down after the fact; that is a flag with who and when, not a delete.

A partial index on visible rows serves every public read, all of which filter
`is_removed = false`.

Additive: nullable or defaulted columns and one index. Safe to apply before the
code that reads them is deployed.

Revision ID: 0043_seller_review_content
Revises: 0042_sellers_and_seller_reviews
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0043_seller_review_content"
down_revision = "0042_sellers_and_seller_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller_reviews", sa.Column("title", sa.String(200)))
    op.add_column("seller_reviews", sa.Column(
        "photo_urls", postgresql.ARRAY(sa.Text()), nullable=False,
        server_default=sa.text("'{}'")))
    op.add_column("seller_reviews", sa.Column(
        "is_removed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("seller_reviews", sa.Column("removed_at", sa.DateTime(timezone=True)))
    op.add_column("seller_reviews", sa.Column(
        "removed_by_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("seller_reviews", sa.Column("removal_note", sa.Text()))
    op.create_index(
        "ix_seller_reviews_visible", "seller_reviews", ["seller_id", "created_at"],
        postgresql_where=sa.text("is_removed = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_seller_reviews_visible", table_name="seller_reviews")
    for column in ("removal_note", "removed_by_id", "removed_at", "is_removed",
                   "photo_urls", "title"):
        op.drop_column("seller_reviews", column)
