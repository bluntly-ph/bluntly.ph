"""Auth request/response schemas (M1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.categories import UnknownCategory, normalize_category
from app.models.enums import Language, MemberRole, MembershipTier, OtpPurpose


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=32,
                                 pattern=r"^[a-z0-9_]+$")
    language: Language = Language.en


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str | None = None
    email: str
    display_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    interests: list[str] | None = None
    role: MemberRole
    membership_tier: MembershipTier
    reputation_score: Decimal
    trust_stage: int
    trust_level_name: str | None = None
    verified_review_count: int = 0
    is_suspended: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class ProfileUpdateIn(BaseModel):
    """Onboarding / profile edit. Omitted fields are left untouched."""

    display_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=32,
                                 pattern=r"^[a-z0-9_]+$")
    interests: list[str] | None = Field(default=None, max_length=20)

    @field_validator("interests")
    @classmethod
    def _known_interests(cls, values: list[str] | None) -> list[str] | None:
        """Interests are category slugs, so they get the same vocabulary.

        The count was bounded and the values were not, so anything at all could
        be stored. `users.interests` is matched against `products.category`
        (lib/interests.ts says so in its own docstring), which means an
        unrecognised interest matches nothing and quietly does nothing - the
        same silent failure the category work existed to end.

        Onboarding offers a subset of the full list, but a reader could
        reasonably be interested in any browsable category, so this validates
        against the whole vocabulary rather than the eight the wizard shows.
        """
        if values is None:
            return None
        cleaned: list[str] = []
        for value in values:
            try:
                slug = normalize_category(value)
            except UnknownCategory as exc:
                raise ValueError(str(exc)) from exc
            if slug and slug not in cleaned:
                cleaned.append(slug)
        return cleaned


class OtpRequestIn(BaseModel):
    email: EmailStr
    purpose: OtpPurpose = OtpPurpose.signup


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
