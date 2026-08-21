"""Shared test fixtures.

The import order in this file is load-bearing. `.env.test` is loaded into the
process environment, and the production guard runs, BEFORE anything from `app`
is imported - because importing `app.core.config` resolves the database URL and
importing `app.db.session` opens an engine against it. A guard that ran after
those imports would be checking a connection that already exists.
"""

from __future__ import annotations

import os
import pathlib
import sys

# --- 1. Load backend/.env.test, if present, into the real environment -------
# pydantic-settings gives actual environment variables precedence over its
# `env_file`, so this is what redirects the suite away from the repo-root .env
# (which is production). Set before any app import.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.core.env_guard import (  # noqa: E402
    ProductionTargetError,
    load_test_env,
    require_non_production,
)

load_test_env()

# --- 2. Refuse to continue if this is production -----------------------------

try:
    require_non_production("pytest")
except ProductionTargetError as exc:  # pragma: no cover - the abort path
    # Raising from conftest import aborts collection before a single test runs,
    # which is the point: no fixture, no user, no review reaches the database.
    raise SystemExit(str(exc)) from exc

# --- 3. Only now is it safe to import the application ------------------------
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

# The suite makes many auth/vote calls from one client IP; lift the rate limits so
# tests aren't self-throttled. (A dedicated limiter test can set them back locally.)
settings.auth_rate_limit_max = 1_000_000
settings.vote_rate_limit_max = 1_000_000

# The suite must never reach Resend: no network, no spend, no codes in transit.
settings.email_provider = "console"
settings.resend_api_key = ""


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


#: Seconds to wait for the probe below. Small on purpose: this decides whether
#: to *skip* tests, so being wrong costs a skipped suite, while being slow costs
#: every run and every CI job.
DB_PROBE_TIMEOUT_SECONDS = 3


def db_available() -> bool:
    """True when a real Postgres is reachable (integration tests).

    Runs at import, because `requires_db` is a module-level marker - so anything
    this blocks on blocks pytest *collection*, before a single test runs.

    It therefore gets its own engine with an explicit connect timeout rather
    than borrowing the application's. A refused connection fails in
    milliseconds, which is why this was fine for a long time; a port that
    silently drops packets instead does not fail at all, and the application
    engine has no timeout to stop it waiting. The symptom is not a failure but
    a hang: no output, no tests, nothing to read - and in CI, a job that sits
    there until the runner kills it.
    """
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    probe = None
    try:
        probe = create_engine(
            settings.effective_database_url,
            connect_args={"connect_timeout": DB_PROBE_TIMEOUT_SECONDS},
            pool_pre_ping=False,
        )
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        if probe is not None:
            probe.dispose()


requires_db = pytest.mark.skipif(
    os.getenv("SKIP_DB_TESTS") == "1" or not db_available(),
    reason="Postgres not available",
)


def find_pending_queue_item(client, mod_headers: dict, review_id: str):
    """Locate a review's card in the moderator queue's `pending` list.

    The queue is a work queue: oldest-first, and a long-lived dev DB accumulates
    thousands of never-published pending reviews, so a fresh review sits on the
    LAST page. Scanning from the front is O(n) pages and each page computes fraud
    signals for every card — far too slow. Instead ask the DB for this review's
    position and fetch exactly that page. We are testing that the endpoint returns
    the card, not that we can scan the whole backlog.
    """
    import uuid as _uuid

    from sqlalchemy import func, select

    from app.db.session import SessionLocal
    from app.models.enums import EarnEligibleStatus
    from app.models.review import Review

    db = SessionLocal()
    try:
        target = db.get(Review, _uuid.UUID(review_id))
        if target is None:
            return None
        pending = (Review.earn_eligible_status == EarnEligibleStatus.pending,
                   Review.published_at.is_(None), Review.is_removed.is_(False))
        # get_queue orders by created_at ASC, so the offset is how many pending
        # reviews were created before this one.
        position = db.scalar(select(func.count(Review.id)).where(
            *pending, Review.created_at < target.created_at)) or 0
    finally:
        db.close()

    for offset in (max(0, position - 2), max(0, position - 25)):
        page = client.get(f"/api/v1/admin/review-queue?limit=50&offset={offset}",
                          headers=mod_headers).json()
        item = next((i for i in page["pending"] if i["review"]["id"] == review_id), None)
        if item is not None:
            return item
    return None


def register_and_token(client, role: str = "user") -> tuple[str, str, str]:
    """Register a fresh user; optionally promote role. Returns (id, token, email)."""
    import uuid

    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.models.enums import MemberRole
    from app.models.user import User

    email = f"t_{uuid.uuid4().hex}@example.com"
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "display_name": "Tester"})
    body = resp.json()
    uid, token = body["user"]["id"], body["access_token"]
    if role != "user":
        db = SessionLocal()
        try:
            user = db.get(User, uuid.UUID(uid))
            user.role = MemberRole(role)
            db.commit()
        finally:
            db.close()
        token = create_access_token(uuid.UUID(uid), role)
    return uid, token, email


def owned_photo_url(headers: dict) -> str:
    """A proof-photo URL the caller in `headers` genuinely owns.

    Reviews used to accept any string as `photo_url`, and since
    verification_status is derived from it being non-null, that made `verified`
    self-assertable - which also unlocks earning eligibility (FR-6) and makes
    FR-8's first fraud layer free to bypass. Ownership is enforced now, so
    fixtures have to hold a real one.

    Derived rather than uploaded: hitting Supabase Storage in every review
    fixture would make the suite slow and network-dependent for a value the
    server only pattern-matches. `upload_review_photo` writes
    `<REVIEW_BUCKET>/<user_id>/<uuid>.<ext>`, and that shape is what is checked.
    """
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app
    from app.services.storage import REVIEW_BUCKET

    uid = TestClient(app).get("/api/v1/auth/me", headers=headers).json()["id"]
    base = (settings.supabase_url or "https://test.supabase.co").rstrip("/")
    return f"{base}/storage/v1/object/public/{REVIEW_BUCKET}/{uid}/{_uuid.uuid4().hex}.jpg"
