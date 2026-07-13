"""Membership-tier routes (M1) — list/get (public), admin config + assignment."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import require_role
from app.db.session import get_db
from app.models.enums import MembershipTier
from app.models.membership import MembershipTierConfig
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.membership import AssignTierRequest, TierOut, TierUpdate

router = APIRouter(tags=["membership"])


@router.get("/membership-tiers", response_model=list[TierOut], summary="List membership tiers")
def list_tiers(db: Session = Depends(get_db)) -> list[TierOut]:
    rows = db.scalars(select(MembershipTierConfig).order_by(MembershipTierConfig.payout_priority))
    return [TierOut.model_validate(t) for t in rows]


@router.get("/membership-tiers/{code}", response_model=TierOut, summary="Get a membership tier")
def get_tier(code: MembershipTier, db: Session = Depends(get_db)) -> TierOut:
    tier = db.scalar(select(MembershipTierConfig).where(MembershipTierConfig.code == code))
    if tier is None:
        raise NotFoundError("Membership tier not found.", code="tier_not_found")
    return TierOut.model_validate(tier)


@router.patch("/membership-tiers/{code}", response_model=TierOut,
              summary="Update a tier's config (moderator)")
def update_tier(code: MembershipTier, payload: TierUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_role("moderator"))) -> TierOut:
    tier = db.scalar(select(MembershipTierConfig).where(MembershipTierConfig.code == code))
    if tier is None:
        raise NotFoundError("Membership tier not found.", code="tier_not_found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tier, field, value)
    db.commit()
    db.refresh(tier)
    return TierOut.model_validate(tier)


@router.patch("/users/{user_id}/membership-tier", response_model=UserOut,
              summary="Assign a membership tier to a user (moderator)")
def assign_tier(user_id: uuid.UUID, payload: AssignTierRequest, db: Session = Depends(get_db),
                _: User = Depends(require_role("moderator"))) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="user_not_found")
    user.membership_tier = payload.membership_tier
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
