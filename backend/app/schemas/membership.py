"""Membership-tier schemas (M1)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MembershipTier
from app.services.earnings import MAX_REVIEWER_SHARE_BPS


class TierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: MembershipTier
    name: str
    description: str | None = None
    revenue_share_bps: int
    payout_priority: int
    benefits: dict | None = None
    is_active: bool


class TierUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    # Bounded by the domain constant, not by 10000. Above
    # MAX_REVIEWER_SHARE_BPS the fixed 30% Honesty Fund leaves the platform
    # share negative, and split_commission_tiered raises ValueError - so a
    # tier saved at 8000 would make every commission for that tier throw,
    # one import batch at a time, long after the change was made.
    revenue_share_bps: int | None = Field(
        default=None, ge=0, le=MAX_REVIEWER_SHARE_BPS)
    payout_priority: int | None = Field(default=None, ge=0)
    benefits: dict | None = None
    is_active: bool | None = None


class AssignTierRequest(BaseModel):
    membership_tier: MembershipTier
