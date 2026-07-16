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
    # The affiliate sub-ID actually set in the dashboard when generating this
    # link. Defaults to the review's suggested sub-ID (see QueueItem). It is what
    # the monthly report echoes back, so it is how the commission gets attributed.
    sub_id: str | None = Field(default=None, max_length=64)


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
    sub_id: str | None = None
    # False = the pasted URL doesn't visibly carry the sub-ID, so this link's
    # commissions will most likely come back unattributable.
    sub_id_in_url: bool = False
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
    # Put THIS in the affiliate dashboard's sub-ID field when generating the link.
    # The marketplace echoes it back in the monthly report and it is the only way
    # the commission can be attributed to this review (M3 slice 12).
    suggested_sub_id: str | None = None


class ReviewQueueResponse(BaseModel):
    pending: list[QueueItem]
    edited_since_monetized: list[QueueItem]
