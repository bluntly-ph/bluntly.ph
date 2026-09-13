"""sellers, seller claims and seller reviews (FR-4)

Reinstates the seller flow. It was built as M2 slice 4, withdrawn by owner
decision on 2026-07-28, and dropped by 0024; the completion contract requires
it, so this brings it back — with one deliberate change of shape.

**Sellers are their own rows, not users.** 0024's table hung `seller_id` off
`users.id`, which can only represent a store that has signed up. FR-4 requires
*unclaimed* profiles — a store buyers have rated but nobody has claimed — so
`sellers` is its own table and `claimed_by_id` is the nullable link to the
account that proved it runs the store. That is the difference between "no
seller yet" and "a seller with no reviews", which the old shape could not tell
apart.

**Claiming is a moderator decision.** `seller_claims` holds the request and the
outcome; `sellers.claim_status` holds the current answer. Two objects rather
than one because a rejected claimant may retry with better evidence, and the
first attempt should not vanish when they do. The partial unique index allows
exactly one *pending* request per person per store while leaving decided ones
in place.

**Ranges are CHECK constraints, not conventions.** FR-4 defines customer
service, packaging and overall as 1-5. A service-layer guard is the wrong
place for that alone: it loses every race and every direct write.

`moderation_target_type.seller_review` already exists — 0024 deliberately left
the enum value in place rather than performing a destructive enum rewrite — so
moderation can target these rows without another enum migration.

Additive: one enum type, three tables, no change to any existing object.

Revision ID: 0042_sellers_and_seller_reviews
Revises: 0041_reading_telemetry
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042_sellers_and_seller_reviews"
down_revision = "0041_reading_telemetry"
branch_labels = None
depends_on = None

CLAIM_STATUS = "seller_claim_status"


def upgrade() -> None:
    postgresql.ENUM(
        "unclaimed", "pending", "claimed", "rejected", name=CLAIM_STATUS
    ).create(op.get_bind(), checkfirst=True)

    # Both enums are bound with create_type=False for the columns below. The
    # type is created once, above; handing create_table an ENUM that still
    # thinks it owns the type makes it emit CREATE TYPE a second time, which
    # is `DuplicateObject: type "seller_claim_status" already exists`.
    # `platform` has the same shape for the opposite reason — it already
    # exists from products / referral_links.
    claim_status = postgresql.ENUM(name=CLAIM_STATUS, create_type=False)
    platform = postgresql.ENUM(name="platform", create_type=False)

    op.create_table(
        "sellers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("platform", platform, nullable=False),
        sa.Column("store_url", sa.Text()),
        sa.Column("claimed_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("claim_status", claim_status, nullable=False,
                  server_default="unclaimed"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("platform", "normalized_name",
                            name="uq_seller_platform_name"),
    )
    op.create_index("ix_sellers_normalized_name", "sellers", ["normalized_name"])
    op.create_index("ix_sellers_claimed_by", "sellers", ["claimed_by_id"])

    op.create_table(
        "seller_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("status", claim_status, nullable=False, server_default="pending"),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_seller_claims_status", "seller_claims", ["status"])
    op.create_index(
        "uq_seller_claim_pending", "seller_claims", ["seller_id", "user_id"],
        unique=True, postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "seller_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("accuracy", sa.Boolean(), nullable=False),
        sa.Column("order_completeness", sa.Boolean(), nullable=False),
        sa.Column("customer_service", sa.SmallInteger(), nullable=False),
        sa.Column("packaging_quality", sa.SmallInteger(), nullable=False),
        sa.Column("overall_rating", sa.SmallInteger(), nullable=False),
        sa.Column("would_recommend", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("seller_id", "reviewer_id", name="uq_seller_review_once"),
        sa.CheckConstraint("customer_service BETWEEN 1 AND 5",
                           name="ck_seller_review_service_range"),
        sa.CheckConstraint("packaging_quality BETWEEN 1 AND 5",
                           name="ck_seller_review_packaging_range"),
        sa.CheckConstraint("overall_rating BETWEEN 1 AND 5",
                           name="ck_seller_review_overall_range"),
    )
    op.create_index("ix_seller_reviews_seller", "seller_reviews",
                    ["seller_id", "created_at"])


def downgrade() -> None:
    op.drop_table("seller_reviews")
    op.drop_table("seller_claims")
    op.drop_table("sellers")
    postgresql.ENUM(name=CLAIM_STATUS).drop(op.get_bind(), checkfirst=True)
