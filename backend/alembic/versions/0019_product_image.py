"""products.image_url / image_source / image_fetched_at

Product listing imagery, so the feed stops rendering hue placeholders. Populated
once by scripts/seed_product_images.py and thereafter by moderators; the running
application never fetches a URL.

Revision ID: 0019_product_image
Revises: 0018_user_interests
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_product_image"
down_revision = "0018_user_interests"
branch_labels = None
depends_on = None

_IMAGE_SOURCE = sa.Enum("seeded", "moderator", "none", name="image_source")


def upgrade() -> None:
    _IMAGE_SOURCE.create(op.get_bind(), checkfirst=True)
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("products", sa.Column(
        "image_source", _IMAGE_SOURCE, nullable=False, server_default="none"))
    op.add_column("products", sa.Column(
        "image_fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_fetched_at")
    op.drop_column("products", "image_source")
    op.drop_column("products", "image_url")
    _IMAGE_SOURCE.drop(op.get_bind(), checkfirst=True)
