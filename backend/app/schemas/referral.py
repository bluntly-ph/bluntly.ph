"""Referral-link flow schemas (M2 slice 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform, ReferralLinkStatus
from app.schemas.review import ReviewOut
from app.services.moderation_priority import PriorityBand, PriorityLane, SlaState


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


# --- Canonical priority assessment (design §5; policy in
# app/services/moderation_priority.py) ---
class QueuePriorityFactor(BaseModel):
    """One explainable contribution to a review's integrity score."""

    code: str
    observed: bool | int | str
    contribution: int
    explanation: str


class QueuePriorityAssessment(BaseModel):
    """Serialized ``PriorityAssessment`` — the moderator-visible reason a review
    sits where it does in the queue. Pure policy output: no telemetry, no PII."""

    policy_version: str
    lane: PriorityLane
    score: int
    band: PriorityBand
    sla_state: SlaState
    due_at: datetime
    factors: list[QueuePriorityFactor] = Field(default_factory=list)


class QueueCounts(BaseModel):
    """Totals over the filtered, ordered candidate set — computed before the
    requested page is sliced, so the UI can show queue depth truthfully even
    while looking at page one."""

    total: int = 0
    by_lane: dict[str, int] = Field(default_factory=dict)
    by_band: dict[str, int] = Field(default_factory=dict)
    by_sla: dict[str, int] = Field(default_factory=dict)


class QueueItem(BaseModel):
    review: ReviewOut
    product: QueueProduct
    author: QueueAuthor | None = None
    suggested_platform: Platform | None = None
    edited_since_monetized: bool = False
    signals: QueueSignals = Field(default_factory=QueueSignals)
    # The canonical priority assessment for this card (design §5). A sibling of
    # `signals`, never a field inside it — `QueueSignals` stays frozen at the
    # advisory six.
    priority: QueuePriorityAssessment
    # Which review timestamp stood in for the (not-yet-migrated) queue-entry
    # time when priority was evaluated: `review.created_at` for an initial
    # pending review, `review.updated_at` for a monetized-but-edited one. The UI
    # must not present either as precise lifecycle timing.
    queue_time_basis: Literal["review_created_at", "review_updated_at"] = "review_created_at"
    # Put THIS in the affiliate dashboard's sub-ID field when generating the link.
    # The marketplace echoes it back in the monthly report and it is the only way
    # the commission can be attributed to this review (M3 slice 12).
    suggested_sub_id: str | None = None


class QueuePage(BaseModel):
    """What ``referral_service.get_prioritized_queue`` returns: one policy-ordered
    page plus the pre-slice totals. The route widens this into
    ``ReviewQueueResponse`` for the compatibility window."""

    items: list[QueueItem] = Field(default_factory=list)
    total: int = 0
    next_cursor: str | None = None
    counts: QueueCounts = Field(default_factory=QueueCounts)


class ReviewQueueResponse(BaseModel):
    # Canonical, server-prioritized slice (design §5). `items` is the full
    # queue ordered by policy — a high-priority review is on page one even if it
    # was created after the first fifty.
    items: list[QueueItem] = Field(default_factory=list)
    total: int = 0
    # Nullable in this compatibility slice: ordering correctness does not depend
    # on the cursor, and offset paging is still accepted. Real cursor paging
    # lands with the queue-entry migration.
    next_cursor: str | None = None
    counts: QueueCounts = Field(default_factory=QueueCounts)
    # --- Deprecated duplicate views (removed once the Next caller in Task 4
    # consumes `items`). Kept so no public endpoint shape changes mid-release. ---
    pending: list[QueueItem] = Field(default_factory=list)
    edited_since_monetized: list[QueueItem] = Field(default_factory=list)
