"""One-time-code issue/verify (Slice 1 Phase A).

Security posture:
  * The plaintext code exists only in memory and in the outbound email; the row
    stores an Argon2id hash.
  * `attempts` lives on the row in Postgres and is incremented in the same
    transaction as the check, so the cap holds when Redis is down — the Redis
    limiter fails open by design and only throttles *sends*.
  * `issue_otp` returns None for every input, including addresses with no
    account, so the endpoint cannot be used to enumerate users.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.email import (
    EmailNotConfigured,
    EmailSendError,
    send_otp_email,
)
from app.core.config import settings
from app.core.errors import (
    EmailDeliveryError,
    OtpAttemptsExceededError,
    OtpExpiredError,
    OtpInvalidError,
    RateLimitError,
)
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.enums import MemberRole, MembershipTier, MemberType, OtpPurpose
from app.models.otp import EmailOtp
from app.models.user import User
from app.services.username import allocate_username

log = get_logger("services.otp")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _generate_code() -> str:
    """A 6-digit code from a CSPRNG. `randbelow` is uniform; `random` is not."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _as_utc(value: datetime) -> datetime:
    """Postgres may hand back naive datetimes depending on the driver path."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def issue_otp(db: Session, email: str, purpose: OtpPurpose) -> None:
    """Issue and send a code. Always returns None — never reveals account state."""
    email = _normalize_email(email)
    user_exists = db.scalar(select(User.id).where(User.email == email)) is not None

    if purpose is OtpPurpose.login and not user_exists:
        # No account: send nothing, store nothing, but return normally so the
        # response is indistinguishable from the success case.
        return
    if purpose is OtpPurpose.signup and user_exists:
        # Already registered: quietly downgrade to a login code rather than
        # leaking that the address is taken.
        purpose = OtpPurpose.login

    now = datetime.now(UTC)

    # Per-address send cap, in Postgres. Redis only throttles by IP and fails
    # open, so this is the authoritative limit on how much mail one address can
    # make us send. Counted before anything is minted or sent.
    window_start = now - timedelta(seconds=settings.otp_send_window_seconds)
    recent = db.scalar(
        select(func.count(EmailOtp.id)).where(
            EmailOtp.email == email, EmailOtp.created_at >= window_start)
    ) or 0
    if recent >= settings.otp_max_sends_per_window:
        oldest = db.scalar(
            select(func.min(EmailOtp.created_at)).where(
                EmailOtp.email == email, EmailOtp.created_at >= window_start))
        retry_after = settings.otp_send_window_seconds
        if oldest is not None:
            elapsed = (now - _as_utc(oldest)).total_seconds()
            retry_after = max(int(settings.otp_send_window_seconds - elapsed), 1)
        log.info("OTP send throttled", extra={
            "extra_fields": {"to": email, "sends_in_window": recent}})
        raise RateLimitError(
            "Too many codes requested for this address. Try again shortly.",
            extra={"retry_after_seconds": retry_after})

    # Requesting a new code invalidates any outstanding one.
    for row in db.scalars(select(EmailOtp).where(
            EmailOtp.email == email, EmailOtp.consumed_at.is_(None))):
        row.consumed_at = now

    code = _generate_code()
    db.add(EmailOtp(
        email=email,
        code_hash=hash_password(code),
        purpose=purpose,
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
    ))

    # Send BEFORE committing. If delivery fails we roll back, so a failed
    # request leaves no orphan code behind and the user can simply retry.
    # (Committing first would strand a live code nobody ever received.)
    try:
        send_otp_email(email, code)
    except (EmailNotConfigured, EmailSendError) as exc:
        db.rollback()
        log.error("OTP email delivery failed", extra={
            "extra_fields": {"to": email, "error": str(exc)}})
        raise EmailDeliveryError(
            "We couldn't send your code right now. Please try again shortly."
        ) from exc
    db.commit()


def verify_otp(db: Session, email: str, code: str) -> User:
    """Consume a code and return the authenticated user, creating it on signup."""
    email = _normalize_email(email)
    now = datetime.now(UTC)
    row = db.scalar(
        select(EmailOtp)
        .where(EmailOtp.email == email, EmailOtp.consumed_at.is_(None))
        .order_by(EmailOtp.created_at.desc())
        .with_for_update()
    )
    if row is None:
        raise OtpInvalidError("That code is not valid.")

    if row.attempts >= settings.otp_max_attempts:
        row.consumed_at = now
        db.commit()
        raise OtpAttemptsExceededError(
            "Too many incorrect attempts. Request a new code.")

    if _as_utc(row.expires_at) <= now:
        row.consumed_at = now
        db.commit()
        raise OtpExpiredError("That code has expired. Request a new one.")

    if not verify_password(code, row.code_hash):
        # Count the attempt before returning — same transaction, no Redis.
        row.attempts += 1
        db.commit()
        raise OtpInvalidError("That code is not valid.")

    row.consumed_at = now
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user_uuid = uuid.uuid4()
        user = User(
            id=user_uuid,
            email=email,
            display_name=None,
            # OTP signup collects no handle, so derive one from the address.
            # The onboarding wizard lets them change it later.
            username=allocate_username(db, None, email, user_uuid),
            role=MemberRole.user,
            member_type=MemberType.shopper,
            membership_tier=MembershipTier.standard,
            user_id=f"usr_{uuid.uuid4().hex[:10]}",
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user
