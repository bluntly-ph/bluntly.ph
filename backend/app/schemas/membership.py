"""Membership-tier schemas (M1)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MembershipTier


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
    revenue_share_bps: int | None = Field(default=None, ge=0, le=10000)
    payout_priority: int | None = Field(default=None, ge=0)
    benefits: dict | None = None
    is_active: bool | None = None


class AssignTierRequest(BaseModel):
    membership_tier: MembershipTier
