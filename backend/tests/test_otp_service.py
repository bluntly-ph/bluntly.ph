"""OTP issue/verify semantics — the security-critical half of Phase A."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import (
    OtpAttemptsExceededError,
    OtpExpiredError,
    OtpInvalidError,
)
from app.db.session import SessionLocal
from app.models.enums import OtpPurpose
from app.models.otp import EmailOtp
from app.services import otp_service
from tests.conftest import requires_db


def _fresh_email() -> str:
    return f"otp-{uuid.uuid4().hex[:12]}@example.com"


def _live_row(db, email: str) -> EmailOtp | None:
    return db.scalar(
        select(EmailOtp).where(EmailOtp.email == email,
                               EmailOtp.consumed_at.is_(None)))


@requires_db
def test_issue_stores_hash_not_plaintext(monkeypatch):
    sent: dict[str, str] = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(to=to, code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        row = _live_row(db, email)
        assert row is not None
        assert sent["code"] != row.code_hash
        assert len(sent["code"]) == 6 and sent["code"].isdigit()
    finally:
        db.close()


@requires_db
def test_verify_happy_path_creates_user_and_is_single_use(monkeypatch):
    sent: dict[str, str] = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        user = otp_service.verify_otp(db, email, sent["code"])
        assert user.email == email
        with pytest.raises(OtpInvalidError):
            otp_service.verify_otp(db, email, sent["code"])
    finally:
        db.close()


@requires_db
def test_expired_code_is_rejected(monkeypatch):
    sent: dict[str, str] = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        row = _live_row(db, email)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(OtpExpiredError):
            otp_service.verify_otp(db, email, sent["code"])
    finally:
        db.close()


@requires_db
def test_attempt_cap_is_enforced_without_redis(monkeypatch):
    """The cap must hold with Redis down — the limiter fails open by design."""
    monkeypatch.setattr(otp_service, "send_otp_email", lambda to, code: None)
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        for _ in range(settings.otp_max_attempts):
            with pytest.raises(OtpInvalidError):
                otp_service.verify_otp(db, email, "000000")
        with pytest.raises(OtpAttemptsExceededError):
            otp_service.verify_otp(db, email, "000000")
    finally:
        db.close()


@requires_db
def test_reissue_invalidates_the_previous_code(monkeypatch):
    codes: list[str] = []
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: codes.append(code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        with pytest.raises(OtpInvalidError):
            otp_service.verify_otp(db, email, codes[0])
        user = otp_service.verify_otp(db, email, codes[1])
        assert user.email == email
    finally:
        db.close()


@requires_db
def test_login_purpose_for_unknown_address_issues_nothing(monkeypatch):
    """Unknown-login addresses get a sign-up signal and no OTP side effects."""
    from app.core.errors import AccountNotFoundError

    monkeypatch.setattr(otp_service, "send_otp_email", lambda to, code: None)
    email = _fresh_email()
    db = SessionLocal()
    try:
        with pytest.raises(AccountNotFoundError):
            otp_service.issue_otp(db, email, OtpPurpose.login)
        assert _live_row(db, email) is None
    finally:
        db.close()


@requires_db
def test_signup_for_existing_address_becomes_a_login_code(monkeypatch):
    """Re-signing-up must not reveal that the address is already registered."""
    sent: dict[str, str] = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        otp_service.verify_otp(db, email, sent["code"])   # user now exists
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        row = _live_row(db, email)
        assert row is not None and row.purpose is OtpPurpose.login
    finally:
        db.close()


@requires_db
def test_delivery_failure_rolls_back_and_raises_a_problem(monkeypatch):
    """A provider rejection must not strand a live code nobody received.

    Regression: send used to happen after commit, and EmailSendError was not an
    AppError — so a rejected send returned a text/plain 500 that escaped the
    RFC 9457 contract entirely, while leaving a usable OTP row behind.
    """
    from app.adapters.email import EmailSendError
    from app.core.errors import EmailDeliveryError

    def _boom(to, code):
        raise EmailSendError("domain not verified")

    monkeypatch.setattr(otp_service, "send_otp_email", _boom)
    email = _fresh_email()
    db = SessionLocal()
    try:
        with pytest.raises(EmailDeliveryError) as exc:
            otp_service.issue_otp(db, email, OtpPurpose.signup)
        assert exc.value.code == "email_send_failed"
        assert exc.value.status_code == 502
        assert _live_row(db, email) is None      # rolled back, no orphan
    finally:
        db.close()


@requires_db
def test_send_throttle_holds_without_redis(monkeypatch):
    """Redis fails open, so a per-address send cap must live in Postgres.

    Without this, /auth/otp/request is an unmetered outbound-email pump during
    any Redis outage: real cost, and a wrecked sending-domain reputation.
    """
    from app.core.errors import RateLimitError

    sends: list[str] = []
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sends.append(to))
    email = _fresh_email()
    db = SessionLocal()
    try:
        for _ in range(settings.otp_max_sends_per_window):
            otp_service.issue_otp(db, email, OtpPurpose.signup)
        assert len(sends) == settings.otp_max_sends_per_window

        with pytest.raises(RateLimitError) as exc:
            otp_service.issue_otp(db, email, OtpPurpose.signup)
        assert exc.value.code == "rate_limited"
        assert exc.value.extra.get("retry_after_seconds", 0) > 0
        # The blocked attempt must not have sent anything.
        assert len(sends) == settings.otp_max_sends_per_window
    finally:
        db.close()


@requires_db
def test_send_throttle_is_per_address(monkeypatch):
    """One address hitting the cap must not lock out everyone else."""
    monkeypatch.setattr(otp_service, "send_otp_email", lambda to, code: None)
    busy, quiet = _fresh_email(), _fresh_email()
    db = SessionLocal()
    try:
        for _ in range(settings.otp_max_sends_per_window):
            otp_service.issue_otp(db, busy, OtpPurpose.signup)
        otp_service.issue_otp(db, quiet, OtpPurpose.signup)   # must not raise
        assert _live_row(db, quiet) is not None
    finally:
        db.close()
