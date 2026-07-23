# Slice 1 Phase A — Backend Auth Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three backend gaps that make the mobile auth design unbuildable — email OTP, a unique `username`, and avatar upload — without disturbing the existing password auth path.

**Architecture:** A new `email_otps` table stores Argon2id hashes of 6-digit codes with a per-row attempt counter, so the verify limit survives a Redis outage. Two new endpoints (`otp/request`, `otp/verify`) return the same `TokenResponse` as `/auth/login`, so the client has one session code path. Email goes out through a provider-swappable adapter (`console` | `resend`) shaped like the existing PayPal adapter. `username` and `avatar_url` are additive columns on `users`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (`Mapped`/`mapped_column`), Alembic, Pydantic v2 + pydantic-settings, Argon2id via `app.core.security`, httpx, pytest, ruff, Supabase Storage.

## Global Constraints

- Migration chain head is `0014_schema_parity`. New revisions chain `0015_email_otp` → `0016_username` → `0017_avatar`.
- Migrations run on the **session** pooler (`:5432`); runtime uses the **transaction** pooler (`:6543`). Session mode caps at 4 clients.
- Every error is RFC 9457 via `AppError` subclasses in `app/core/errors.py`. Clients branch on `code`, never on message text.
- All files start with `from __future__ import annotations`.
- `python` is venv-only: run `backend/.venv/Scripts/python` (Windows) — a bare `python` is not on PATH.
- The test suite must pin `EMAIL_PROVIDER=console`. **No test may make a network call to Resend.**
- Existing counts must not regress: 159 tests, 49/49 `verify_milestones`, 59/59 `supabase_verify`.
- Never store an OTP code in plaintext.
- Redis rate limiting **fails open** by design (`app/core/rate_limit.py:53`). It may throttle *sends*; it must never be the only thing limiting *verifies*.

---

### Task 1: Email adapter + settings

**Files:**
- Create: `backend/app/adapters/email.py`
- Modify: `backend/app/core/config.py` (settings block after line 158; startup guard near line 266)
- Test: `backend/tests/test_email_adapter.py`

**Interfaces:**
- Consumes: `settings` from `app.core.config`, `get_logger` from `app.core.logging`.
- Produces:
  - `send_otp_email(to: str, code: str) -> None`
  - `EmailNotConfigured(RuntimeError)`
  - `EmailSendError(RuntimeError)`
  - settings fields: `email_provider: str`, `resend_api_key: str`, `email_from: str`, `otp_ttl_seconds: int`, `otp_max_attempts: int`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_email_adapter.py`:

```python
"""Email adapter — provider switching and failure modes."""

from __future__ import annotations

import pytest

from app.adapters import email as email_adapter
from app.core.config import settings


def test_console_provider_logs_and_does_not_raise(caplog):
    settings.email_provider = "console"
    with caplog.at_level("INFO"):
        email_adapter.send_otp_email("someone@example.com", "123456")
    assert "123456" in caplog.text


def test_resend_provider_without_key_raises():
    settings.email_provider = "resend"
    settings.resend_api_key = ""
    try:
        with pytest.raises(email_adapter.EmailNotConfigured):
            email_adapter.send_otp_email("someone@example.com", "123456")
    finally:
        settings.email_provider = "console"


def test_unknown_provider_raises():
    settings.email_provider = "carrier-pigeon"
    try:
        with pytest.raises(email_adapter.EmailNotConfigured):
            email_adapter.send_otp_email("someone@example.com", "123456")
    finally:
        settings.email_provider = "console"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_email_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.adapters.email'`

- [ ] **Step 3: Add the settings**

In `backend/app/core/config.py`, directly after the PayPal block (currently ending line 158), add:

```python
    # --- Email + OTP (Slice 1 Phase A) ---
    email_provider: str = "console"      # console | resend
    resend_api_key: str = ""
    email_from: str = "onboarding@resend.dev"
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
```

- [ ] **Step 4: Add the production startup guard**

In `backend/app/core/config.py`, inside the same validation method that holds the `paypal_live` checks (around line 266), append:

```python
        if self.app_env == "production" and self.email_provider == "console":
            issues.append("APP_ENV=production requires a real EMAIL_PROVIDER "
                          "(console only logs codes; OTP would never be delivered).")
        if self.email_provider == "resend" and not self.resend_api_key:
            issues.append("EMAIL_PROVIDER=resend requires RESEND_API_KEY.")
```

- [ ] **Step 5: Write the adapter**

Create `backend/app/adapters/email.py`:

```python
"""Email delivery adapter (Slice 1 Phase A).

Mirrors the shape of `adapters/paypal.py`: the adapter never touches the
database and never decides policy — it sends and reports.

Two providers:
  * `console` — logs the code. The local and TEST default; makes OTP fully
    developable and testable with no vendor key and no network.
  * `resend`  — POST https://api.resend.com/emails with a Bearer key.

Missing credentials raise `EmailNotConfigured` rather than silently no-oping,
so a misconfigured production box fails loudly instead of swallowing codes.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("adapters.email")

RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT = httpx.Timeout(10.0)

_SUBJECT = "Your bluntly verification code"


class EmailNotConfigured(RuntimeError):
    """Provider missing or unknown — caller should surface a 500, not a 2xx."""


class EmailSendError(RuntimeError):
    """The provider rejected the request or was unreachable."""


def _body(code: str) -> str:
    ttl_minutes = max(settings.otp_ttl_seconds // 60, 1)
    return (
        f"Your bluntly verification code is {code}.\n\n"
        f"It expires in {ttl_minutes} minutes. "
        "If you didn't request it, you can ignore this email."
    )


def send_otp_email(to: str, code: str) -> None:
    """Deliver a one-time code. Raises on misconfiguration or provider failure."""
    provider = settings.email_provider
    if provider == "console":
        # Deliberately logs the code: this provider exists so developers and the
        # test suite can complete an OTP round trip offline.
        log.info("OTP email (console provider)", extra={
            "extra_fields": {"to": to, "code": code}})
        return
    if provider != "resend":
        raise EmailNotConfigured(f"Unknown EMAIL_PROVIDER {provider!r}.")
    if not settings.resend_api_key:
        raise EmailNotConfigured("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty.")

    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": _SUBJECT,
                "text": _body(code),
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Resend unreachable: {exc}") from exc
    if response.status_code >= 400:
        # Never log the code on the failure path.
        raise EmailSendError(
            f"Resend rejected the send ({response.status_code}): {response.text}")
```

- [ ] **Step 6: Pin the test provider**

In `backend/tests/conftest.py`, directly below the existing rate-limit overrides (after `settings.vote_rate_limit_max = 1_000_000`), add:

```python
# The suite must never hit Resend: no network, no spend, no leaked codes.
settings.email_provider = "console"
settings.resend_api_key = ""
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_email_adapter.py -v`
Expected: PASS, 3 passed

- [ ] **Step 8: Lint and commit**

```bash
cd backend && .venv/Scripts/python -m ruff check app tests
git add backend/app/adapters/email.py backend/app/core/config.py backend/tests/test_email_adapter.py backend/tests/conftest.py
git commit -m "feat(auth): email adapter with console and resend providers"
```

---

### Task 2: `email_otps` model and migration

**Files:**
- Create: `backend/app/models/otp.py`
- Create: `backend/alembic/versions/0015_email_otp.py`
- Modify: `backend/app/models/enums.py` (append `OtpPurpose`)
- Modify: `backend/app/db/base.py` or wherever models are imported for metadata — verify `app/models/__init__.py` imports every model module, and add `otp`
- Test: `backend/tests/test_otp_model.py`

**Interfaces:**
- Consumes: `Base`, `Timestamps` from `app.db.base`.
- Produces:
  - `class OtpPurpose(str, Enum)` with members `signup`, `login`
  - `class EmailOtp(Base)` with columns `id`, `email`, `code_hash`, `purpose`, `attempts`, `expires_at`, `consumed_at`, `created_at`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_otp_model.py`:

```python
"""email_otps table shape."""

from __future__ import annotations

from app.models.enums import OtpPurpose
from app.models.otp import EmailOtp


def test_purpose_enum_members():
    assert {m.value for m in OtpPurpose} == {"signup", "login"}


def test_table_columns():
    cols = set(EmailOtp.__table__.columns.keys())
    assert cols == {
        "id", "email", "code_hash", "purpose", "attempts",
        "expires_at", "consumed_at", "created_at",
    }


def test_code_is_never_stored_plaintext():
    # A `code` column would mean plaintext storage; only the hash may exist.
    assert "code" not in EmailOtp.__table__.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'OtpPurpose'`

- [ ] **Step 3: Add the enum**

Append to `backend/app/models/enums.py`:

```python
class OtpPurpose(str, Enum):
    signup = "signup"
    login = "login"
```

- [ ] **Step 4: Add the model**

Create `backend/app/models/otp.py`:

```python
"""email_otps — one-time codes for passwordless auth (Slice 1 Phase A).

`email` is deliberately NOT a foreign key to `users`: a signup code is issued
before the user row exists.

`attempts` is the authoritative verify limit. The Redis limiter fails open by
design (app/core/rate_limit.py), so a Redis outage must not hand an attacker
unlimited guesses at a 6-digit code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OtpPurpose


class EmailOtp(Base):
    __tablename__ = "email_otps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    # Argon2id, via app.core.security.hash_password. Never the plaintext code.
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(
        Enum(OtpPurpose, name="otp_purpose"), nullable=False)
    attempts: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False)
```

- [ ] **Step 5: Register the model for metadata**

In `backend/app/models/__init__.py`, add the import in alphabetical position
(between `moderation` on line 11 and `payout` on line 12):

```python
from app.models.otp import EmailOtp  # noqa: F401
```

and append `"EmailOtp"` to the `__all__` list (after `"Payout"`, line 29).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_model.py -v`
Expected: PASS, 3 passed

- [ ] **Step 7: Write the migration**

Create `backend/alembic/versions/0015_email_otp.py`:

```python
"""email_otps — one-time codes for passwordless auth (Slice 1 Phase A)

The partial unique-ish index on (email, purpose) WHERE consumed_at IS NULL
supports the hot path: "find this address's live code". Requesting a new code
consumes any outstanding one, so at most a handful of rows match.

Revision ID: 0015_email_otp
Revises: 0014_schema_parity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_email_otp"
down_revision = "0014_schema_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    otp_purpose = sa.Enum("signup", "login", name="otp_purpose")
    otp_purpose.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_otps",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", otp_purpose, nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_otps_email", "email_otps", ["email"])
    op.execute("CREATE INDEX ix_email_otps_live ON email_otps (email, purpose) "
               "WHERE consumed_at IS NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_otps_live")
    op.drop_index("ix_email_otps_email", table_name="email_otps")
    op.drop_table("email_otps")
    sa.Enum(name="otp_purpose").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 8: Apply the migration**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: `Running upgrade 0014_schema_parity -> 0015_email_otp`

Verify: `cd backend && .venv/Scripts/python -m alembic current`
Expected: output contains `0015_email_otp (head)`

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/otp.py backend/app/models/enums.py backend/app/models/__init__.py backend/alembic/versions/0015_email_otp.py backend/tests/test_otp_model.py
git commit -m "feat(auth): email_otps table with hashed codes and attempt counter"
```

---

### Task 3: OTP service

**Files:**
- Create: `backend/app/services/otp_service.py`
- Modify: `backend/app/core/errors.py` (append OTP error classes)
- Test: `backend/tests/test_otp_service.py`

**Interfaces:**
- Consumes: `EmailOtp`, `OtpPurpose`, `hash_password`/`verify_password` from `app.core.security`, `send_otp_email` from `app.adapters.email`, `register_user`-adjacent helpers from `app.services.auth_service`.
- Produces:
  - `issue_otp(db: Session, email: str, purpose: OtpPurpose) -> None`
  - `verify_otp(db: Session, email: str, code: str) -> User`
  - `OtpInvalidError`, `OtpExpiredError`, `OtpAttemptsExceededError`

- [ ] **Step 1: Add the error classes**

Append to `backend/app/core/errors.py`:

```python
class OtpInvalidError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "otp_invalid"
    title = "Invalid verification code"


class OtpExpiredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "otp_expired"
    title = "Verification code expired"


class OtpAttemptsExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "otp_attempts_exceeded"
    title = "Too many verification attempts"
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_otp_service.py`:

```python
"""OTP issue/verify semantics — the security-critical half of Phase A."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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


def _live_row(db, email: str) -> EmailOtp:
    return db.scalar(
        select(EmailOtp).where(EmailOtp.email == email,
                               EmailOtp.consumed_at.is_(None)))


@requires_db
def test_issue_stores_hash_not_plaintext(monkeypatch):
    sent = {}
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
def test_verify_happy_path_creates_user_on_signup(monkeypatch):
    sent = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        user = otp_service.verify_otp(db, email, sent["code"])
        assert user.email == email
        # single-use
        with pytest.raises(OtpInvalidError):
            otp_service.verify_otp(db, email, sent["code"])
    finally:
        db.close()


@requires_db
def test_expired_code_is_rejected(monkeypatch):
    sent = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    db = SessionLocal()
    try:
        otp_service.issue_otp(db, email, OtpPurpose.signup)
        row = _live_row(db, email)
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(OtpExpiredError):
            otp_service.verify_otp(db, email, sent["code"])
    finally:
        db.close()


@requires_db
def test_attempt_cap_is_enforced_without_redis(monkeypatch):
    """The cap must hold even with Redis down — the limiter fails open."""
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
    codes = []
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
def test_login_purpose_requires_existing_user(monkeypatch):
    monkeypatch.setattr(otp_service, "send_otp_email", lambda to, code: None)
    email = _fresh_email()
    db = SessionLocal()
    try:
        # No user exists; issuing must not raise (no enumeration) ...
        otp_service.issue_otp(db, email, OtpPurpose.login)
        # ... and no code row is created for an unknown address.
        assert _live_row(db, email) is None
    finally:
        db.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.otp_service'`

- [ ] **Step 4: Write the service**

Create `backend/app/services/otp_service.py`:

```python
"""One-time-code issue/verify (Slice 1 Phase A).

Security posture:
  * The plaintext code exists only in memory and in the outbound email.
  * `attempts` lives on the row in Postgres and is incremented in the same
    transaction as the check, so the cap holds when Redis is down — the Redis
    limiter fails open by design and only throttles sends.
  * `issue_otp` returns None for every input, including addresses with no
    account, so the endpoint cannot be used to enumerate users.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.email import send_otp_email
from app.core.config import settings
from app.core.errors import (
    OtpAttemptsExceededError,
    OtpExpiredError,
    OtpInvalidError,
)
from app.core.security import hash_password, verify_password
from app.models.enums import MemberRole, MembershipTier, MemberType, OtpPurpose
from app.models.otp import EmailOtp
from app.models.user import User


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_otp(db: Session, email: str, purpose: OtpPurpose) -> None:
    """Issue and send a code. Always returns None — never reveals account state."""
    email = _normalize_email(email)
    user_exists = db.scalar(select(User.id).where(User.email == email)) is not None

    if purpose is OtpPurpose.login and not user_exists:
        # No account: send nothing, store nothing, but return normally so the
        # caller's response is indistinguishable from the success case.
        return
    if purpose is OtpPurpose.signup and user_exists:
        # Already registered: fall back to a login code rather than leaking that
        # the address is taken.
        purpose = OtpPurpose.login

    # Requesting a new code invalidates any outstanding one.
    now = datetime.now(timezone.utc)
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
    db.commit()
    send_otp_email(email, code)


def verify_otp(db: Session, email: str, code: str) -> User:
    """Consume a code and return the authenticated user, creating it on signup."""
    email = _normalize_email(email)
    now = datetime.now(timezone.utc)
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

    if row.expires_at <= now:
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
        user = User(
            email=email,
            display_name=None,
            role=MemberRole.user,
            member_type=MemberType.shopper,
            membership_tier=MembershipTier.standard,
            user_id=f"usr_{uuid.uuid4().hex[:10]}",
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_service.py -v`
Expected: PASS, 6 passed

- [ ] **Step 6: Lint and commit**

```bash
cd backend && .venv/Scripts/python -m ruff check app tests
git add backend/app/services/otp_service.py backend/app/core/errors.py backend/tests/test_otp_service.py
git commit -m "feat(auth): OTP issue/verify with DB-enforced attempt cap"
```

---

### Task 4: OTP endpoints

**Files:**
- Modify: `backend/app/api/v1/routes/auth.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_otp_api.py`

**Interfaces:**
- Consumes: `issue_otp`, `verify_otp` from `app.services.otp_service`; `_token_response` (already defined at `auth.py:24`).
- Produces: `POST /api/v1/auth/otp/request`, `POST /api/v1/auth/otp/verify`; schemas `OtpRequestIn`, `OtpVerifyIn`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_otp_api.py`:

```python
"""OTP endpoints — contract and non-enumeration."""

from __future__ import annotations

import uuid

from app.services import otp_service
from tests.conftest import requires_db

BASE = "/api/v1/auth"


def _fresh_email() -> str:
    return f"otpapi-{uuid.uuid4().hex[:12]}@example.com"


@requires_db
def test_request_returns_202_for_unknown_address(client):
    r = client.post(f"{BASE}/otp/request",
                    json={"email": _fresh_email(), "purpose": "login"})
    assert r.status_code == 202


@requires_db
def test_signup_round_trip_returns_token(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(otp_service, "send_otp_email",
                        lambda to, code: sent.update(code=code))
    email = _fresh_email()
    r = client.post(f"{BASE}/otp/request", json={"email": email, "purpose": "signup"})
    assert r.status_code == 202

    r = client.post(f"{BASE}/otp/verify", json={"email": email, "code": sent["code"]})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert body["expires_in"] > 0

    me = client.get(f"{BASE}/me",
                    headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


@requires_db
def test_wrong_code_returns_problem_json_with_code(client, monkeypatch):
    monkeypatch.setattr(otp_service, "send_otp_email", lambda to, code: None)
    email = _fresh_email()
    client.post(f"{BASE}/otp/request", json={"email": email, "purpose": "signup"})
    r = client.post(f"{BASE}/otp/verify", json={"email": email, "code": "000000"})
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "otp_invalid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_api.py -v`
Expected: FAIL — 404 on `/auth/otp/request`

- [ ] **Step 3: Add the schemas**

Append to `backend/app/schemas/auth.py`:

```python
class OtpRequestIn(BaseModel):
    email: EmailStr
    purpose: OtpPurpose = OtpPurpose.signup


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
```

and extend the existing enum import at the top of the file:

```python
from app.models.enums import Language, MemberRole, MembershipTier, OtpPurpose
```

- [ ] **Step 4: Add the routes**

In `backend/app/api/v1/routes/auth.py`, extend the imports:

```python
from app.schemas.auth import (
    OtpRequestIn, OtpVerifyIn, RegisterRequest, TokenResponse, UserOut,
)
from app.services.otp_service import issue_otp, verify_otp
```

and append the routes after `login` (before `me`):

```python
@router.post("/otp/request", status_code=202, responses=_PROBLEM,
             summary="Request a one-time login/signup code by email")
def otp_request(payload: OtpRequestIn, db: Session = Depends(get_db),
                _: None = Depends(auth_rate_limiter("otp_request"))) -> dict[str, str]:
    # Always 202, whether or not the address has an account — anything else
    # turns this endpoint into a user-enumeration oracle.
    issue_otp(db, payload.email, payload.purpose)
    return {"status": "sent"}


@router.post("/otp/verify", response_model=TokenResponse, responses=_PROBLEM,
             summary="Exchange a one-time code for an access token")
def otp_verify(payload: OtpVerifyIn, db: Session = Depends(get_db),
               _: None = Depends(auth_rate_limiter("otp_verify"))) -> TokenResponse:
    user = verify_otp(db, payload.email, payload.code)
    if user.is_suspended:
        raise AuthError("Account is suspended.", code="account_suspended",
                        status_code=403)
    return _token_response(user)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_otp_api.py -v`
Expected: PASS, 3 passed

- [ ] **Step 6: Commit**

```bash
cd backend && .venv/Scripts/python -m ruff check app tests
git add backend/app/api/v1/routes/auth.py backend/app/schemas/auth.py backend/tests/test_otp_api.py
git commit -m "feat(auth): OTP request and verify endpoints"
```

---

### Task 5: `username` column, backfill, and validation

**Files:**
- Create: `backend/alembic/versions/0016_username.py`
- Create: `backend/app/services/username.py`
- Modify: `backend/app/models/user.py` (after `display_name`, line 60)
- Modify: `backend/app/schemas/auth.py` (`UserOut`, `RegisterRequest`)
- Modify: `backend/app/services/auth_service.py` (`register_user`)
- Test: `backend/tests/test_username.py`

**Interfaces:**
- Produces:
  - `slugify_username(raw: str) -> str`
  - `allocate_username(db: Session, preferred: str | None, email: str, user_id: uuid.UUID) -> str`
  - `User.username: Mapped[str | None]`
  - `UserOut.username: str | None`
  - error code `username_taken` (409)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_username.py`:

```python
"""Username slugification, allocation, and uniqueness."""

from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.services.username import allocate_username, slugify_username
from tests.conftest import requires_db


@pytest.mark.parametrize("raw,expected", [
    ("Viole Was Here", "viole_was_here"),
    ("  Ana  Cruz  ", "ana_cruz"),
    ("JuanDelaCruz", "juandelacruz"),
    ("a!!!b???c", "a_b_c"),
    ("____x____", "x"),
    ("Ñoño", "nono"),        # NFKD + ascii-fold drops the tilde, not the letter
])
def test_slugify(raw, expected):
    assert slugify_username(raw) == expected


def test_slugify_truncates_to_32():
    assert len(slugify_username("x" * 100)) == 32


@requires_db
def test_allocate_dedupes_on_collision():
    db = SessionLocal()
    try:
        uid = uuid.uuid4()
        first = allocate_username(db, "collide_me", "a@example.com", uid)
        assert first == "collide_me"
        # Simulate the name now being taken by inserting a user with it.
        from app.models.enums import MemberRole, MembershipTier, MemberType
        from app.models.user import User
        db.add(User(email=f"{uuid.uuid4().hex}@example.com", username=first,
                    role=MemberRole.user, member_type=MemberType.shopper,
                    membership_tier=MembershipTier.standard))
        db.commit()
        second = allocate_username(db, "collide_me", "b@example.com", uuid.uuid4())
        assert second == "collide_me2"
    finally:
        db.rollback()
        db.close()


@requires_db
def test_allocate_falls_back_to_email_local_part():
    db = SessionLocal()
    try:
        name = allocate_username(db, None, "Fallback.User@example.com", uuid.uuid4())
        assert name.startswith("fallback_user")
    finally:
        db.close()


def test_slugify_returns_empty_for_unusable_input():
    """Punctuation-only input yields nothing; callers must fall back."""
    assert slugify_username("!!!") == ""


@requires_db
def test_allocate_falls_back_when_preferred_is_unusable():
    db = SessionLocal()
    try:
        uid = uuid.uuid4()
        # "!!!" slugs to "" (too short), so allocation must skip to the
        # email local-part rather than producing an empty handle.
        name = allocate_username(db, "!!!", "usable.name@example.com", uid)
        assert name.startswith("usable_name")
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_username.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.username'`

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/user.py`, directly after the `display_name` line (currently line 60), add:

```python
    # Stable public handle (Slice 1 Phase A). display_name remains the free-text
    # label; username is the unique, URL-safe identity shown as @handle.
    username: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
```

- [ ] **Step 4: Write the username service**

Create `backend/app/services/username.py`:

```python
"""Username slugification and collision-safe allocation (Slice 1 Phase A)."""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User

MAX_LENGTH = 32
MIN_LENGTH = 3
_VALID = re.compile(r"^[a-z0-9_]{%d,%d}$" % (MIN_LENGTH, MAX_LENGTH))


def slugify_username(raw: str) -> str:
    """Lowercase, ASCII-fold, collapse invalid runs to `_`, trim to 32."""
    folded = unicodedata.normalize("NFKD", raw)
    folded = folded.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower())
    slug = re.sub(r"_{2,}", "_", slug).strip("_")
    return slug[:MAX_LENGTH]


def is_valid_username(candidate: str) -> bool:
    return bool(_VALID.match(candidate))


def _taken(db: Session, candidate: str) -> bool:
    return db.scalar(
        select(User.id).where(func.lower(User.username) == candidate)) is not None


def allocate_username(db: Session, preferred: str | None, email: str,
                      user_id: uuid.UUID) -> str:
    """Pick a free handle: preferred -> email local-part -> user_<short id>."""
    candidates = []
    if preferred:
        candidates.append(slugify_username(preferred))
    candidates.append(slugify_username(email.split("@", 1)[0]))
    candidates.append(f"user_{user_id.hex[:8]}")

    for base in candidates:
        if len(base) < MIN_LENGTH:
            continue
        if not _taken(db, base):
            return base
        for suffix in range(2, 1000):
            trimmed = base[: MAX_LENGTH - len(str(suffix))]
            candidate = f"{trimmed}{suffix}"
            if not _taken(db, candidate):
                return candidate
    # Exhausted: fall back to a value that cannot collide.
    return f"user_{uuid.uuid4().hex[:16]}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_username.py -v`
Expected: PASS, 10 passed

- [ ] **Step 6: Write the migration**

Create `backend/alembic/versions/0016_username.py`:

```python
"""users.username — unique public handle (Slice 1 Phase A)

Three-phase so it is safe on a populated table: add nullable, backfill a
deterministic slug for every existing row, then constrain. The backfill mirrors
app/services/username.py: slugify(display_name) -> email local-part ->
user_<short id>, with a numeric suffix on collision.

Revision ID: 0016_username
Revises: 0015_email_otp
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_username"
down_revision = "0015_email_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))

    # Phase 2 — backfill. regexp_replace mirrors the Python slugifier:
    # lowercase, non-alphanumerics to '_', collapse runs, trim, cap at 32.
    # ROW_NUMBER over the slug partition gives collision suffixes; rn = 1 keeps
    # the bare slug so the common case reads naturally.
    op.execute("""
        WITH slugged AS (
            SELECT id,
                   COALESCE(
                     NULLIF(
                       LEFT(
                         TRIM(BOTH '_' FROM
                           REGEXP_REPLACE(
                             REGEXP_REPLACE(
                               LOWER(COALESCE(NULLIF(TRIM(display_name), ''),
                                              split_part(email, '@', 1))),
                               '[^a-z0-9]+', '_', 'g'),
                             '_{2,}', '_', 'g')),
                         32),
                       ''),
                     'user') AS base
            FROM users
        ), numbered AS (
            SELECT id, base,
                   ROW_NUMBER() OVER (PARTITION BY base ORDER BY id) AS rn
            FROM slugged
        )
        UPDATE users u
           SET username = CASE
                            WHEN n.rn = 1 THEN n.base
                            ELSE LEFT(n.base, 32 - LENGTH(n.rn::text))
                                 || n.rn::text
                          END
          FROM numbered n
         WHERE u.id = n.id AND u.username IS NULL
    """)

    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "username", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
```

> **Note:** rows whose backfilled `base` is shorter than 3 characters remain
> valid at the DB level — the `is_valid_username` 3–32 rule governs
> *user-supplied* values only, never the backfill. Tightening it would fail the
> migration on legitimate short display names.

- [ ] **Step 7: Apply and verify the backfill**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: `Running upgrade 0015_email_otp -> 0016_username`

Verify uniqueness and completeness:

```bash
cd backend && .venv/Scripts/python -c "
from sqlalchemy import text
from app.db.session import engine
with engine.connect() as c:
    total = c.execute(text('SELECT count(*) FROM users')).scalar()
    distinct = c.execute(text('SELECT count(DISTINCT username) FROM users')).scalar()
    nulls = c.execute(text('SELECT count(*) FROM users WHERE username IS NULL')).scalar()
    print(f'total={total} distinct={distinct} nulls={nulls}')
    assert nulls == 0 and total == distinct, 'backfill failed'
    print('backfill OK')
"
```
Expected: `backfill OK`

- [ ] **Step 8: Expose username through the API**

In `backend/app/schemas/auth.py`, add to `UserOut` after `display_name`:

```python
    username: str | None = None
```

and to `RegisterRequest` after `display_name`:

```python
    username: str | None = Field(default=None, min_length=3, max_length=32,
                                 pattern=r"^[a-z0-9_]+$")
```

In `backend/app/services/auth_service.py`, extend `register_user`. Replace the
`user = User(...)` block with:

```python
    user_uuid = uuid.uuid4()
    if payload.username and _username_taken(db, payload.username):
        raise AppError("That username is already taken.", code="username_taken",
                       status_code=409, title="Username already registered")
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
```

and add the import plus helper:

```python
from sqlalchemy import func

from app.services.username import allocate_username


def _username_taken(db: Session, candidate: str) -> bool:
    return db.scalar(
        select(User.id).where(func.lower(User.username) == candidate.lower())
    ) is not None
```

Apply the same `allocate_username` call in `otp_service.verify_otp` where the
new `User(...)` is constructed, so OTP signups also get a handle:

```python
        user_uuid = uuid.uuid4()
        user = User(
            id=user_uuid,
            email=email,
            display_name=None,
            username=allocate_username(db, None, email, user_uuid),
            role=MemberRole.user,
            member_type=MemberType.shopper,
            membership_tier=MembershipTier.standard,
            user_id=f"usr_{uuid.uuid4().hex[:10]}",
        )
```

- [ ] **Step 9: Run the full suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: all previously passing tests still pass; new tests pass.

- [ ] **Step 10: Commit**

```bash
cd backend && .venv/Scripts/python -m ruff check app tests
git add backend/app/models/user.py backend/app/services/username.py backend/app/services/auth_service.py backend/app/services/otp_service.py backend/app/schemas/auth.py backend/alembic/versions/0016_username.py backend/tests/test_username.py
git commit -m "feat(auth): unique username column with deterministic backfill"
```

---

### Task 6: Avatar upload

**Files:**
- Create: `backend/alembic/versions/0017_avatar.py`
- Create: `backend/app/services/storage.py`
- Create: `backend/app/api/v1/routes/users_me.py`
- Modify: `backend/app/models/user.py`, `backend/app/schemas/auth.py`, `backend/app/api/v1/__init__.py` (router registration)
- Test: `backend/tests/test_avatar.py`

**Interfaces:**
- Produces:
  - `upload_avatar(user_id: uuid.UUID, data: bytes, content_type: str) -> str`
  - `delete_avatar_object(url: str) -> None`
  - `User.avatar_url: Mapped[str | None]`, `UserOut.avatar_url: str | None`
  - `POST /api/v1/users/me/avatar`, `DELETE /api/v1/users/me/avatar`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_avatar.py`:

```python
"""Avatar upload validation. Storage itself is stubbed — we test our rules."""

from __future__ import annotations

import io
import uuid

import pytest

from app.core.errors import AppError
from app.services import storage

PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def test_sniffed_type_wins_over_declared_type():
    # A .png claim over JPEG bytes must resolve to jpeg, not png.
    assert storage.sniff_image_type(JPEG_MAGIC) == "image/jpeg"
    assert storage.sniff_image_type(PNG_MAGIC) == "image/png"


def test_non_image_is_rejected():
    with pytest.raises(AppError) as exc:
        storage.validate_avatar(b"GIF89a" + b"\x00" * 64)
    assert exc.value.code == "unsupported_media_type"


def test_oversize_is_rejected():
    too_big = PNG_MAGIC + b"\x00" * (5 * 1024 * 1024)
    with pytest.raises(AppError) as exc:
        storage.validate_avatar(too_big)
    assert exc.value.code == "file_too_large"


def test_valid_png_passes():
    assert storage.validate_avatar(PNG_MAGIC) == "image/png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_avatar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.storage'`

- [ ] **Step 3: Write the storage service**

Create `backend/app/services/storage.py`:

```python
"""Supabase Storage helpers (Slice 1 Phase A).

This is the first real Storage integration — supabase_client.py has carried the
clients since M0 with no consumer. Kept generic so review photos can reuse it.

Content type is sniffed from magic bytes, never trusted from the client: a
browser-supplied Content-Type is attacker-controlled.
"""

from __future__ import annotations

import uuid

from app.core.errors import AppError
from app.core.supabase_client import get_service_client

AVATAR_BUCKET = "avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024

_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"RIFF", "image/webp", "webp"),   # RIFF....WEBP
)


def sniff_image_type(data: bytes) -> str | None:
    for magic, mime, _ in _MAGIC:
        if data.startswith(magic):
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    return None


def _extension_for(mime: str) -> str:
    for _, m, ext in _MAGIC:
        if m == mime:
            return ext
    raise AppError("Unsupported image type.", code="unsupported_media_type",
                   status_code=415)


def validate_avatar(data: bytes) -> str:
    """Return the sniffed MIME type, or raise an AppError."""
    if len(data) > MAX_AVATAR_BYTES:
        raise AppError("Avatar must be 5 MB or smaller.", code="file_too_large",
                       status_code=413, title="File too large")
    mime = sniff_image_type(data)
    if mime is None:
        raise AppError("Avatar must be a PNG, JPEG, or WebP image.",
                       code="unsupported_media_type", status_code=415,
                       title="Unsupported media type")
    return mime


def upload_avatar(user_id: uuid.UUID, data: bytes) -> str:
    """Store the object and return its public URL."""
    mime = validate_avatar(data)
    path = f"{user_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    bucket = get_service_client().storage.from_(AVATAR_BUCKET)
    bucket.upload(path, data, {"content-type": mime, "upsert": "false"})
    return bucket.get_public_url(path)


def delete_avatar_object(url: str) -> None:
    """Best-effort removal of a previously uploaded object."""
    marker = f"/{AVATAR_BUCKET}/"
    if marker not in url:
        return
    path = url.split(marker, 1)[1].split("?", 1)[0]
    try:
        get_service_client().storage.from_(AVATAR_BUCKET).remove([path])
    except Exception:  # noqa: BLE001 — a stale object must not fail the request
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_avatar.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Add the column and migration**

In `backend/app/models/user.py`, after the `username` line added in Task 5:

```python
    avatar_url: Mapped[str | None] = mapped_column(Text)
```

Create `backend/alembic/versions/0017_avatar.py`:

```python
"""users.avatar_url — profile image in Supabase Storage (Slice 1 Phase A)

Revision ID: 0017_avatar
Revises: 0016_username
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_avatar"
down_revision = "0016_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
```

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: `Running upgrade 0016_username -> 0017_avatar`

- [ ] **Step 6: Add the endpoints**

Add `avatar_url: str | None = None` to `UserOut` in `backend/app/schemas/auth.py`.

Create `backend/app/api/v1/routes/users_me.py`:

```python
"""Current-user profile mutations (Slice 1 Phase A)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.common import Problem
from app.services.storage import delete_avatar_object, upload_avatar

router = APIRouter(prefix="/users/me", tags=["users"])

_PROBLEM = {401: {"model": Problem}, 413: {"model": Problem},
            415: {"model": Problem}}


@router.post("/avatar", response_model=UserOut, responses=_PROBLEM,
             summary="Upload or replace the current user's avatar")
def set_avatar(file: UploadFile, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> UserOut:
    data = file.file.read()
    new_url = upload_avatar(user.id, data)
    previous = user.avatar_url
    user.avatar_url = new_url
    db.commit()
    db.refresh(user)
    if previous:
        delete_avatar_object(previous)
    return UserOut.model_validate(user)


@router.delete("/avatar", status_code=204, responses=_PROBLEM,
               summary="Remove the current user's avatar")
def clear_avatar(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> None:
    previous = user.avatar_url
    user.avatar_url = None
    db.commit()
    if previous:
        delete_avatar_object(previous)
```

Register it where the other v1 routers are included (`backend/app/api/v1/__init__.py`
or `router.py` — match the existing pattern):

```python
from app.api.v1.routes import users_me
api_router.include_router(users_me.router)
```

- [ ] **Step 7: Create the storage bucket**

In the Supabase dashboard, create a **public** bucket named `avatars`. Verify:

```bash
cd backend && .venv/Scripts/python -c "
from app.core.supabase_client import get_service_client
names = [b.name for b in get_service_client().storage.list_buckets()]
print(names); assert 'avatars' in names, 'create the avatars bucket'
print('bucket OK')
"
```
Expected: `bucket OK`

- [ ] **Step 8: Run the full suite and commit**

```bash
cd backend && .venv/Scripts/python -m pytest -q && .venv/Scripts/python -m ruff check app tests
git add backend/app/services/storage.py backend/app/api/v1/routes/users_me.py backend/app/models/user.py backend/app/schemas/auth.py backend/alembic/versions/0017_avatar.py backend/tests/test_avatar.py
git commit -m "feat(auth): avatar upload to Supabase Storage"
```

---

### Task 7: Regenerate contracts and update docs

**Files:**
- Modify: `docs/openapi.json` (generated), `lib/api-types.d.ts` (generated)
- Modify: `docs/schema.md`, `docs/FRONTEND_INTEGRATION.md`, `docs/DEVIATIONS.md`

- [ ] **Step 1: Regenerate the spec and types**

```bash
cd backend && .venv/Scripts/python -m scripts.export_openapi
cd .. && npm run gen:api
```
Expected: `docs/openapi.json` gains 4 paths (`/auth/otp/request`, `/auth/otp/verify`, `/users/me/avatar` ×2); `lib/api-types.d.ts` regenerates.

- [ ] **Step 2: Verify the contract test still passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_openapi_contract.py -v`
Expected: PASS

- [ ] **Step 3: Update `docs/schema.md`**

Add the `email_otps` table (all 8 columns, per Task 2) and the two new `users`
columns (`username`, `avatar_url`). Note that `schema.md` was already known to
lag by 3 M3 tables (`request_upvotes`, `review_contracts`, `review_requests`) —
add those at the same time so the document is finally accurate.

- [ ] **Step 4: Update `docs/FRONTEND_INTEGRATION.md`**

In §2 (Auth), document the OTP pair and that both it and `/auth/login` return an
identical `TokenResponse`. In §3's error table, add:

| code | status | What the UI should do |
|---|---|---|
| `otp_invalid` | 409 | Clear the input, let them retry, show attempts remaining. |
| `otp_expired` | 409 | Offer "send a new code". |
| `otp_attempts_exceeded` | 429 | Force a new code request; the old one is dead. |
| `username_taken` | 409 | Mark the username field, suggest an alternative. |
| `unsupported_media_type` | 415 | Explain PNG/JPEG/WebP only. |
| `file_too_large` | 413 | Explain the 5 MB cap. |

- [ ] **Step 5: Record the deviations**

Append to `docs/DEVIATIONS.md`: OTP is delivered by **email**, not SMS — the
Figma copy says "We'll text you a code" but the only input on the frame is an
email field, so the copy is corrected in the UI. Also note the `bluntly.ph` +
checkmark desktop logo is dropped in favour of the `bluntly` wordmark
everywhere.

- [ ] **Step 6: Full verification and commit**

```bash
cd backend
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check app tests
.venv/Scripts/python -m scripts.verify_milestones
.venv/Scripts/python -m scripts.supabase_verify
```
Expected: all tests pass (159 + ~26 new), ruff clean, 49/49, 59/59.

```bash
git add docs/ lib/api-types.d.ts
git commit -m "docs: regenerate OpenAPI and document the new auth surface"
```

---

## Phase A Done When

- [ ] `pytest` green, with the pre-existing 159 tests unregressed.
- [ ] `ruff check app tests` clean.
- [ ] `alembic current` reports `0017_avatar (head)` on both local Postgres and Supabase.
- [ ] The `0016` backfill produced a unique, non-null handle for every existing user.
- [ ] `verify_milestones` 49/49 and `supabase_verify` 59/59.
- [ ] An end-to-end OTP round trip completes with `EMAIL_PROVIDER=console`.
- [ ] No test performs a network call to Resend.
