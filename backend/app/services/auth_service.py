"""Registration & authentication (M1, ADR-010)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models.enums import MemberRole, MembershipTier, MemberType
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.username import allocate_username


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _username_taken(db: Session, candidate: str) -> bool:
    return db.scalar(
        select(User.id).where(func.lower(User.username) == candidate.lower())
    ) is not None


def register_user(db: Session, payload: RegisterRequest) -> User:
    email = _normalize_email(payload.email)
    exists = db.scalar(select(User.id).where(User.email == email))
    if exists:
        raise AppError("An account with this email already exists.",
                       code="email_taken", status_code=409, title="Email already registered")
    # An explicitly requested handle that is taken is a real 409 — silently
    # handing back `viole2` when someone asked for `viole` would be worse.
    if payload.username and _username_taken(db, payload.username):
        raise AppError("That username is already taken.", code="username_taken",
                       status_code=409, title="Username already registered")
    user_uuid = uuid.uuid4()
    user = User(
        id=user_uuid,
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        username=allocate_username(db, payload.username, email, user_uuid),
        language=payload.language,
        role=MemberRole.user,
        member_type=MemberType.shopper,
        membership_tier=MembershipTier.standard,
        user_id=f"usr_{uuid.uuid4().hex[:10]}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == _normalize_email(email)))
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
