"""User trust profile + moderator role management (M2 slices 3-4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, NotFoundError
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import MemberRole, ModerationAction, ModerationTargetType
from app.models.moderation import ModerationLog
from app.models.user import User, UserBadge
from app.schemas.auth import ProfileUpdateIn, UserOut
from app.schemas.common import Problem
from app.schemas.user import BadgeOut, RoleUpdate, UserTrustOut
from app.services.storage import delete_avatar_object, upload_avatar

router = APIRouter(prefix="/users", tags=["users"])

_AVATAR_PROBLEM = {401: {"model": Problem}, 413: {"model": Problem},
                   415: {"model": Problem}}


def _user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="user_not_found")
    return user


# Registered before the `/{user_id}/...` routes so the literal `me` segment is
# never considered as a UUID path parameter.
@router.patch("/me", response_model=UserOut,
              responses={401: {"model": Problem}, 409: {"model": Problem}},
              summary="Update the current user's profile")
def update_me(payload: ProfileUpdateIn, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> UserOut:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.username is not None and payload.username != user.username:
        clash = db.scalar(select(User.id).where(
            func.lower(User.username) == payload.username.lower(),
            User.id != user.id))
        if clash is not None:
            raise AppError("That username is already taken.",
                           code="username_taken", status_code=409,
                           title="Username already registered")
        user.username = payload.username
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/me/avatar", response_model=UserOut, responses=_AVATAR_PROBLEM,
             summary="Upload or replace the current user's avatar")
def set_avatar(file: UploadFile, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> UserOut:
    data = file.file.read()
    new_url = upload_avatar(user.id, data)
    previous = user.avatar_url
    user.avatar_url = new_url
    db.commit()
    db.refresh(user)
    # Only drop the old object once the new one is committed — a failure here
    # must never leave the user with no avatar at all.
    if previous:
        delete_avatar_object(previous)
    return UserOut.model_validate(user)


@router.delete("/me/avatar", status_code=204, responses=_AVATAR_PROBLEM,
               # response_model=None: without it FastAPI infers a model from the
               # `-> None` annotation, which a 204 may not carry.
               response_model=None, summary="Remove the current user's avatar")
def clear_avatar(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> None:
    previous = user.avatar_url
    user.avatar_url = None
    db.commit()
    if previous:
        delete_avatar_object(previous)


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
