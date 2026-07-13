"""Auth request/response schemas (M1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Language, MemberRole, MembershipTier


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    language: Language = Language.en


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str | None = None
    email: str
    display_name: str | None = None
    role: MemberRole
    membership_tier: MembershipTier
    reputation_score: Decimal
    trust_stage: int
    trust_level_name: str | None = None
    is_suspended: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut
