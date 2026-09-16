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


class PublicProfileOut(BaseModel):
    """A reviewer's public identity, resolvable by handle (BUG-030).

    The public profile lives at `/u/{handle}`, and QA reported it 404ing for
    every real reviewer. Two reasons, both here:

      * the page resolved a reviewer through the review feed's `author_id`,
        which takes a UUID — so a handle like `/u/ciel` could never match;
      * a reviewer with no PUBLISHED review has no feed row at all, so an
        account that plainly exists answered "not found".

    This resolves either spelling and does not depend on the reviewer having
    published anything. What it deliberately does NOT carry is as much the
    point as what it does: no email, no role, no staff flags, no earnings, no
    interests. `/u/{handle}` is a page a stranger can open.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    trust_stage: int
    trust_level_name: str
    reputation_score: Decimal
    verified_review_count: int
    #: Published, not removed. Zero is a real answer — see the docstring.
    review_count: int = 0
    created_at: datetime


class TrustProgressOut(BaseModel):
    """How far this member is from the next trust stage.

    The profile's Stats card (Figma 5446:6532) draws a progress bar and a
    "x of y" caption. The ladder lives in `app.services.trust`; serving the
    numbers rather than the thresholds keeps the frontend from carrying a second
    copy of it that can drift.

    `null` on the whole object means the member is at the top stage — there is
    nothing further to progress towards, which is not the same as zero progress.
    """

    next_stage: int
    next_level_name: str
    reviews_have: int
    reviews_needed: int


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
    progress: TrustProgressOut | None = None


class RoleUpdate(BaseModel):
    """Moderator promote/demote between user and seller (M2 slice 4).

    `moderator` is intentionally not grantable via the API.
    """

    role: MemberRole


