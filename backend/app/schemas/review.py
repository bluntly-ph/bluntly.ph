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


class ReviewCreate(BaseModel):
    product_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    discussion: str = Field(min_length=1)
    verdict: Verdict
    verdict_explanation: str | None = None
    target_audience: str | None = None
    anti_target_audience: str | None = None
    star_rating: int = Field(ge=1, le=5)
    pros: list[str] = Field(default_factory=list, max_length=10)
    cons: list[str] = Field(default_factory=list, max_length=10)
    photo_url: str | None = None
    receipt_url: str | None = None
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
    receipt_url: str | None = None
    price_paid: Decimal | None = None
    change_note: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    receipt_url: str | None = None
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


class FeedProduct(BaseModel):
    """The product fields a public card needs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name: str | None = None
    category: str | None = None
    avg_rating: Decimal = Decimal("0")
    review_count: int = 0


class FeedItemOut(BaseModel):
    """A published review joined with its author and product.

    The reviews list returns a bare ReviewOut (no author/product), which every
    card surface (landing, search, category, profile) then cannot render. This
    is the read-side join for those surfaces; the raw ReviewOut is unchanged.
    """

    review: ReviewOut
    author: FeedAuthor | None = None
    product: FeedProduct | None = None


class ReviewVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_number: int
    snapshot: dict
    edited_by: uuid.UUID | None = None
    change_note: str | None = None
    created_at: datetime
