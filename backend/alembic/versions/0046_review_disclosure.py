"""disclosure of a material relationship on reviews (completion contract X.1)

A reviewer declares whether they bought the product themselves, received it
free or discounted, or are connected to the brand or seller. Readers see the
last two on the review.

**Existing reviews get NULL, not "none".** They were written before the
question existed. Defaulting them to "none" would record a declaration their
authors never made, so NULL means "never asked" and the page shows nothing.

Additive: one enum type and one nullable column.

Revision ID: 0046_review_disclosure
Revises: 0045_seller_questions
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0046_review_disclosure"
down_revision = "0045_seller_questions"
branch_labels = None
depends_on = None

ENUM_NAME = "material_relationship"


def upgrade() -> None:
    postgresql.ENUM("none", "free_or_discounted", "connected",
                    name=ENUM_NAME).create(op.get_bind(), checkfirst=True)
    op.add_column("reviews", sa.Column(
        "material_relationship", postgresql.ENUM(name=ENUM_NAME, create_type=False)))


def downgrade() -> None:
    op.drop_column("reviews", "material_relationship")
    postgresql.ENUM(name=ENUM_NAME).drop(op.get_bind(), checkfirst=True)
