"""Review + version-history schemas (M1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import EarnEligibleStatus, Verdict, VerificationStatus, VoteDirection


class VoteIn(BaseModel):
    """Community helpfulness vote (M2 slice 2)."""

    vote: VoteDirection


# Ceiling on the review body (BUG-022). QA submitted ~5,100 characters with no
# limit, warning, or truncation. Roughly 800 words — generous for a product
# review, and enforced here as well as in the form so the cap is a property of
# the API rather than a courtesy of one client.
MAX_DISCUSSION_CHARS = 5000


class ReviewCreate(BaseModel):
    product_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    discussion: str = Field(min_length=1, max_length=MAX_DISCUSSION_CHARS)
    verdict: Verdict
    verdict_explanation: str | None = None
    target_audience: str | None = None
    anti_target_audience: str | None = None
    star_rating: int = Field(ge=1, le=5)
    pros: list[str] = Field(default_factory=list, max_length=10)
    cons: list[str] = Field(default_factory=list, max_length=10)
    photo_url: str | None = None
    # Object key from POST /reviews/receipt, not a URL. The route verifies the
    # key was uploaded by this caller before it is stored.
    receipt_key: str | None = None
    price_paid: Decimal | None = None


class ReviewUpdate(BaseModel):
    """All fields optional; any change creates a new version."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    discussion: str | None = Field(default=None, min_length=1)
    verdict: Verdict | None = None
    verdict_explanation: str | None = None
    target_audience: str | None = None
    anti_target_audience: str | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)
    pros: list[str] | None = Field(default=None, max_length=10)
    cons: list[str] | None = Field(default=None, max_length=10)
    photo_url: str | None = None
    receipt_key: str | None = None
    price_paid: Decimal | None = None
    change_note: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The requesting viewer's own vote, or None for signed-out readers and for
    # anyone who hasn't voted (BUG-013). Not a column — the route fills it in
    # after validation, because it is a fact about the *viewer*, not the review.
    # Without it the vote buttons had no way to know they were already pressed,
    # so the highlight vanished on every refresh and voting again looked broken.
    my_vote: VoteDirection | None = None

    id: uuid.UUID
    review_id: str | None = None
    product_id: uuid.UUID
    author_id: uuid.UUID | None = None
    title: str
    discussion: str
    verdict: Verdict
    verdict_explanation: str | None = None
    target_audience: str | None = None
    anti_target_audience: str | None = None
    star_rating: int
    pros: list | None = None
    cons: list | None = None
    photo_url: str | None = None
    # Deliberately NO receipt locator on any response model.
    #
    # This schema is returned by GET /reviews and GET /reviews/{id}, both of
    # which accept anonymous callers, so anything on it is public for every
    # published review. `has_receipt` is the harmless half of the fact - it
    # says evidence was submitted without saying where it lives. A moderator
    # or the author fetches the object itself from GET /reviews/{id}/receipt.
    has_receipt: bool = False
    price_paid: Decimal | None = None
    verification_status: VerificationStatus
    # Community visibility voting (M2 slice 2).
    helpful_votes: int = 0
    unhelpful_votes: int = 0
    wilson_score: Decimal = Decimal("0")
    current_version: int
    # Publication gate (M2 slice 1): NULL until a moderator publishes.
    published_at: datetime | None = None
    earn_eligible_status: EarnEligibleStatus
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def referral_redirect_url(self) -> str | None:
        """Public attribution link — exposed instead of the raw affiliate URL.
        Only present once the review is published AND monetized."""
        monetized = self.earn_eligible_status == EarnEligibleStatus.monetized
        if self.published_at is not None and monetized:
            return f"/r/{self.id}"
        return None


class FeedAuthor(BaseModel):
    """The author fields a public card needs (never email or wallet data)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    trust_stage: int = 0
    trust_level_name: str | None = None
    # 0..100 (ADR-003). The card shows the number beside the level name, because
    # the level name alone is not a score — stage 2 is literally called
    # "Verified Buyer", which is what BUG-004 was reading as a hardcoded label.
    reputation_score: Decimal = Decimal("0")


class FeedProduct(BaseModel):
    """The product fields a public card needs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name: str | None = None
    category: str | None = None
    avg_rating: Decimal = Decimal("0")
    review_count: int = 0
    # The listing image (BUG-009). The column and its seeding script have existed
    # since the product-image work, but nothing ever put it on the wire, so every
    # card fell through to the placeholder no matter how well-populated the
    # database was. Distinct from a review's own photo, which takes precedence.
    image_url: str | None = None


class FeedItemOut(BaseModel):
    """A published review joined with its author and product.

    The reviews list returns a bare ReviewOut (no author/product), which every
    card surface (landing, search, category, profile) then cannot render. This
    is the read-side join for those surfaces; the raw ReviewOut is unchanged.
    """

    review: ReviewOut
    author: FeedAuthor | None = None
    product: FeedProduct | None = None
    # Populated by the route (BUG-006). The card draws an upvote count beside a
    # comment count; the comment half had no source on the wire at all, so the
    # frontend hardcoded it empty and the stat silently never appeared.
    comment_count: int = 0


class ReviewVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_number: int
    snapshot: dict
    edited_by: uuid.UUID | None = None
    change_note: str | None = None
    created_at: datetime
