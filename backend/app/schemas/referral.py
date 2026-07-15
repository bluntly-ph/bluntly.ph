"""Referral-link flow schemas (M2 slice 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform, ReferralLinkStatus
from app.schemas.review import ReviewOut


class AttachLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    platform: Platform


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class OptionalReasonRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReferralLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_id: uuid.UUID
    platform: Platform
    url: str
    status: ReferralLinkStatus
    review_version: int
    created_by: uuid.UUID | None = None
    revoked_by: uuid.UUID | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    created_at: datetime


# --- Moderator queue ---
class QueuePlatform(BaseModel):
    platform: Platform
    is_monetizable: bool


class QueueProduct(BaseModel):
    id: uuid.UUID
    canonical_name: str | None = None
    source_url: str | None = None
    platforms: list[QueuePlatform] = Field(default_factory=list)


class QueueAuthor(BaseModel):
    id: uuid.UUID
    display_name: str | None = None
    trust_stage: int
    reputation_score: Decimal


class QueueSignals(BaseModel):
    """Advisory fraud signals (M2 slice 5) — moderator queue only, never public,
    never auto-blocking."""

    velocity: bool = False
    collusion: bool = False
    duplicate_content: bool = False
    duplicate_of: str | None = None
    author_account_age_days: int = 0
    author_review_count: int = 0


class QueueItem(BaseModel):
    review: ReviewOut
    product: QueueProduct
    author: QueueAuthor | None = None
    suggested_platform: Platform | None = None
    edited_since_monetized: bool = False
    signals: QueueSignals = Field(default_factory=QueueSignals)


class ReviewQueueResponse(BaseModel):
    pending: list[QueueItem]
    edited_since_monetized: list[QueueItem]
