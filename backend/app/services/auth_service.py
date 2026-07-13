"""Registration & authentication (M1, ADR-010)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models.enums import MemberRole, MembershipTier, MemberType
from app.models.user import User
from app.schemas.auth import RegisterRequest


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, payload: RegisterRequest) -> User:
    email = _normalize_email(payload.email)
    exists = db.scalar(select(User.id).where(User.email == email))
    if exists:
        raise AppError("An account with this email already exists.",
                       code="email_taken", status_code=409, title="Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
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
