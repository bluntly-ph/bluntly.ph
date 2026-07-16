"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

# The suite makes many auth/vote calls from one client IP; lift the rate limits so
# tests aren't self-throttled. (A dedicated limiter test can set them back locally.)
settings.auth_rate_limit_max = 1_000_000
settings.vote_rate_limit_max = 1_000_000


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def db_available() -> bool:
    """True when a real Postgres is reachable (integration tests)."""
    from sqlalchemy import text

    from app.db.session import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


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
