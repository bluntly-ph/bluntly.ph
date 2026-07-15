"""User trust profile + moderator role management (M2 slices 3-4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, NotFoundError
from app.core.security import require_role
from app.db.session import get_db
from app.models.enums import MemberRole, ModerationAction, ModerationTargetType
from app.models.moderation import ModerationLog
from app.models.user import User, UserBadge
from app.schemas.auth import UserOut
from app.schemas.user import BadgeOut, RoleUpdate, UserTrustOut

router = APIRouter(prefix="/users", tags=["users"])


def _user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="user_not_found")
    return user


@router.get("/{user_id}/trust", response_model=UserTrustOut,
            summary="Public trust profile (stage, reputation, badges)")
def get_trust(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserTrustOut:
    user = _user_or_404(db, user_id)
    user_badges = db.scalars(
        select(UserBadge).where(UserBadge.user_id == user.id)
        .options(joinedload(UserBadge.badge))
        .order_by(UserBadge.awarded_at)
    ).all()
    return UserTrustOut(
        id=user.id,
        trust_stage=user.trust_stage,
        trust_level_name=user.trust_level_name,
        reputation_score=user.reputation_score,
        verified_review_count=user.verified_review_count,
        helpfulness_ratio=user.helpfulness_ratio,
        badges=[BadgeOut(badge_id=ub.badge.badge_id, name=ub.badge.name,
                         awarded_at=ub.awarded_at) for ub in user_badges],
    )


@router.patch("/{user_id}/role", response_model=UserOut,
              summary="Promote/demote seller (moderator only)")
def set_role(user_id: uuid.UUID, payload: RoleUpdate, db: Session = Depends(get_db),
             moderator: User = Depends(require_role("moderator"))) -> UserOut:
    if payload.role == MemberRole.moderator:
        raise AppError("The moderator role cannot be granted via the API.",
                       code="role_not_grantable", status_code=422,
                       title="Invalid role")
    user = _user_or_404(db, user_id)
    old_role = user.role
    user.role = payload.role
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.user, target_ref=user.id,
        moderator_id=moderator.id, action=ModerationAction.override,
        notes="role change",
        context={"from": old_role.value, "to": payload.role.value},
    ))
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
