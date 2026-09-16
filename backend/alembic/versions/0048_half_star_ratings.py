"""half-star ratings, and zero as a real answer (owner requirement 2026-09-16)

Ratings were whole stars, 1 to 5, enforced by `ck_review_star_rating` and
`ck_seller_review_overall_range`. The owner's requirement is 0, 0.5, 1 … 5:
half steps, and zero as an intentional rating rather than "unanswered".

So the two star columns become `numeric(2,1)` and their range checks are
replaced by ones that also pin the step:

    value BETWEEN 0 AND 5 AND (value * 2) = trunc(value * 2)

`star_rating_at_view` follows, so a telemetry row keeps the rating a reader
actually saw instead of truncating a half away.

Widening is safe for existing rows: every whole number is representable, and
`numeric(2,1)` holds 0.0 … 5.0 exactly (no float, so no 4.4999 surprises).
The two graded seller dimensions — customer service and packaging — keep their
1..5 integers: the frame draws them as numbered chips, not stars, and nothing
in the requirement asks a chip row to grow half steps.

The downgrade rounds halves to the nearest whole star, which is lossy; it is
written so the schema can go back, not so the data can.

Revision ID: 0048_half_star_ratings
Revises: 0047_notifications
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0048_half_star_ratings"
down_revision = "0047_notifications"
branch_labels = None
depends_on = None

HALF_STEP = "{col} >= 0 AND {col} <= 5 AND ({col} * 2) = trunc({col} * 2)"


def upgrade() -> None:
    # reviews.star_rating -----------------------------------------------------
    op.drop_constraint("ck_review_star_rating", "reviews", type_="check")
    op.alter_column(
        "reviews",
        "star_rating",
        type_=sa.Numeric(2, 1),
        existing_type=sa.SmallInteger(),
        existing_nullable=False,
        postgresql_using="star_rating::numeric(2,1)",
    )
    op.create_check_constraint(
        "ck_review_star_rating", "reviews", HALF_STEP.format(col="star_rating")
    )

    # seller_reviews.overall_rating ------------------------------------------
    op.drop_constraint("ck_seller_review_overall_range", "seller_reviews", type_="check")
    op.alter_column(
        "seller_reviews",
        "overall_rating",
        type_=sa.Numeric(2, 1),
        existing_type=sa.SmallInteger(),
        existing_nullable=False,
        postgresql_using="overall_rating::numeric(2,1)",
    )
    op.create_check_constraint(
        "ck_seller_review_overall_range",
        "seller_reviews",
        HALF_STEP.format(col="overall_rating"),
    )

    # the rating a reader saw, in the same units --------------------------------
    op.alter_column(
        "review_reading_sessions",
        "star_rating_at_view",
        type_=sa.Numeric(2, 1),
        existing_type=sa.SmallInteger(),
        existing_nullable=True,
        postgresql_using="star_rating_at_view::numeric(2,1)",
    )


def downgrade() -> None:
    op.alter_column(
        "review_reading_sessions",
        "star_rating_at_view",
        type_=sa.SmallInteger(),
        existing_type=sa.Numeric(2, 1),
        existing_nullable=True,
        postgresql_using="round(star_rating_at_view)::smallint",
    )

    op.drop_constraint("ck_seller_review_overall_range", "seller_reviews", type_="check")
    op.execute("UPDATE seller_reviews SET overall_rating = GREATEST(round(overall_rating), 1)")
    op.alter_column(
        "seller_reviews",
        "overall_rating",
        type_=sa.SmallInteger(),
        existing_type=sa.Numeric(2, 1),
        existing_nullable=False,
        postgresql_using="round(overall_rating)::smallint",
    )
    op.create_check_constraint(
        "ck_seller_review_overall_range", "seller_reviews", "overall_rating BETWEEN 1 AND 5"
    )

    op.drop_constraint("ck_review_star_rating", "reviews", type_="check")
    op.execute("UPDATE reviews SET star_rating = GREATEST(round(star_rating), 1)")
    op.alter_column(
        "reviews",
        "star_rating",
        type_=sa.SmallInteger(),
        existing_type=sa.Numeric(2, 1),
        existing_nullable=False,
        postgresql_using="round(star_rating)::smallint",
    )
    op.create_check_constraint("ck_review_star_rating", "reviews", "star_rating BETWEEN 1 AND 5")
