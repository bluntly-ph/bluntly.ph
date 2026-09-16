"""Sellers, the claim workflow, and seller reviews (FR-4).

Built as M2 slice 4, withdrawn by owner decision on 2026-07-28 (migration 0024
dropped `seller_reviews`), and reinstated by the completion contract, which
requires the seller flow rather than treating it as optional.

**A seller is not a user.** The withdrawn design hung `seller_reviews.seller_id`
off `users.id`, which works only if every seller has an account. FR-4 requires
*unclaimed* profiles — a store that has been reviewed by buyers but has never
signed up — so the store is its own row and `claimed_by_id` is the nullable
link to whoever proved they run it. Reusing `users` would have made "unclaimed"
unrepresentable.

**Claims are moderator-approved, never automatic.** FR-4 limits seller
verification to "cross-checking store names on submitted proof of purchase
against publicly visible marketplace listings", and the completion contract
says not to invent identity verification. So a claim is a request with evidence
that a moderator decides; nothing in this module grants ownership on its own.

**One seller review per (seller, reviewer).** Enforced in the database, not
only in the service, because a duplicate rating is the cheapest way to move an
aggregate and a service-only guard loses every race.

The four dimensions are FR-4's, and their types carry the specification: the
two binary judgements are booleans (accuracy: accurate / not the same;
completeness: exact order / missing item) and the two graded ones are 1-5, as
is the overall rating.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Numeric,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import Platform, SellerClaimStatus


class Seller(UUIDPrimaryKey, Timestamps, Base):
    """A store on a marketplace. May exist with nobody behind it."""

    __tablename__ = "sellers"
    __table_args__ = (
        # The same store name on two marketplaces is two sellers; the same name
        # twice on one marketplace is a duplicate, and duplicates split a
        # rating in half.
        UniqueConstraint("platform", "normalized_name", name="uq_seller_platform_name"),
        Index("ix_sellers_claimed_by", "claimed_by_id"),
    )

    #: As the store writes it, for display.
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    #: Casefolded and whitespace-collapsed, for the uniqueness constraint. The
    #: service owns the normalisation so the rule is one function, not a habit.
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform"), nullable=False
    )
    #: The store's own page, when a reviewer supplied one. Never scraped.
    store_url: Mapped[str | None] = mapped_column(Text)

    #: Null until a moderator approves a claim. This is the only field that
    #: says a real person speaks for this store.
    claimed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    claim_status: Mapped[SellerClaimStatus] = mapped_column(
        Enum(SellerClaimStatus, name="seller_claim_status"),
        default=SellerClaimStatus.unclaimed,
        server_default=SellerClaimStatus.unclaimed.value,
        nullable=False,
    )



class SellerClaim(UUIDPrimaryKey, Base):
    """A request to speak for a store, and the moderator's decision on it.

    Kept separate from `sellers.claim_status` on purpose: the seller row holds
    the current answer, this holds how it was reached and who decided. A
    rejected claimant can try again with better evidence without the first
    attempt disappearing.
    """

    __tablename__ = "seller_claims"
    __table_args__ = (
        # One *live* request per person per store. A decided one does not block
        # a retry, which is why this is partial rather than a plain unique.
        Index(
            "uq_seller_claim_pending",
            "seller_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_seller_claims_status", "status"),
    )

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    #: What the claimant says makes them the owner. Free text on purpose: the
    #: moderator cross-checks it against the public listing, and a fixed set of
    #: fields would only invite a fixed set of lies.
    evidence: Mapped[str | None] = mapped_column(Text)

    status: Mapped[SellerClaimStatus] = mapped_column(
        Enum(SellerClaimStatus, name="seller_claim_status"),
        default=SellerClaimStatus.pending,
        server_default=SellerClaimStatus.pending.value,
        nullable=False,
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SellerReview(UUIDPrimaryKey, Timestamps, Base):
    """A verified buyer's rating of a store, on FR-4's four dimensions.

    Displayed separately from product reviews and carrying no affiliate link:
    nothing here earns, which is why these publish without the moderation gate
    that product reviews go through (`docs/DEVIATIONS.md` §37).
    """

    __tablename__ = "seller_reviews"
    __table_args__ = (
        UniqueConstraint("seller_id", "reviewer_id", name="uq_seller_review_once"),
        CheckConstraint(
            "customer_service BETWEEN 1 AND 5", name="ck_seller_review_service_range"
        ),
        CheckConstraint(
            "packaging_quality BETWEEN 1 AND 5", name="ck_seller_review_packaging_range"
        ),
        CheckConstraint(
            "overall_rating >= 0 AND overall_rating <= 5"
            " AND (overall_rating * 2) = trunc(overall_rating * 2)",
            name="ck_seller_review_overall_range",
        ),
        Index("ix_seller_reviews_seller", "seller_id", "created_at"),
    )

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    #: SET NULL rather than CASCADE: a deleted account should not silently
    #: revise a store's rating history.
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    #: What was bought, when the reviewer said. Context for a reader, and the
    #: link back to the purchase the rating is about.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )

    #: true = matched the advertisement, false = not the same.
    accuracy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: true = exact order, false = something missing.
    order_completeness: Mapped[bool] = mapped_column(Boolean, nullable=False)
    customer_service: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    packaging_quality: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: 0 to 5 in half steps (0048); the two graded dimensions above stay
    #: whole numbers, because the frame draws them as numbered chips.
    overall_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    would_recommend: Mapped[bool] = mapped_column(Boolean, nullable=False)

    #: Added by 0043. The composer caps it at 30; the column allows 200.
    title: Mapped[str | None] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)
    #: Public URLs from POST /reviews/photo, each checked as the reviewer's own.
    photo_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'"), nullable=False
    )

    #: Moderator removal (0043). A flag rather than a delete, so the audit trail
    #: survives and the unique constraint still blocks a straight re-post.
    is_removed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    removal_note: Mapped[str | None] = mapped_column(Text)
