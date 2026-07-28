"""User-facing trust/profile schemas (M2 slices 3-4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MemberRole


class BadgeOut(BaseModel):
    badge_id: str
    name: str
    awarded_at: datetime


class UserTrustOut(BaseModel):
    """Public trust profile (M2 slice 3). Stages move only via recompute."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trust_stage: int
    trust_level_name: str
    reputation_score: Decimal
    verified_review_count: int
    helpfulness_ratio: Decimal
    badges: list[BadgeOut] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Moderator promote/demote between user and seller (M2 slice 4).

    `moderator` is intentionally not grantable via the API.
    """

    role: MemberRole


