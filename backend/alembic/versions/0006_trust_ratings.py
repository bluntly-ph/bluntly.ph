"""product + seller trust ratings (M2 slice 4)

- products.trust_score: time-decayed Wilson over published reviews (stars >= 4).
- users.seller_trust_score: time-decayed Wilson over seller_reviews.would_recommend.
- uq_seller_review_once: one seller review per (seller, reviewer).

Revision ID: 0006_trust_ratings
Revises: 0005_review_votes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_trust_ratings"
down_revision = "0005_review_votes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column(
        "trust_score", sa.Numeric(6, 5), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("seller_trust_score", sa.Numeric(6, 5), nullable=True))
    op.create_unique_constraint(
        "uq_seller_review_once", "seller_reviews", ["seller_id", "reviewer_id"])


def downgrade() -> None:
    op.drop_constraint("uq_seller_review_once", "seller_reviews", type_="unique")
    op.drop_column("users", "seller_trust_score")
    op.drop_column("products", "trust_score")
