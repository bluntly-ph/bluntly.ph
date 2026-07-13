"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

# The suite makes many auth calls from one client IP; lift the auth rate limit so
# tests aren't self-throttled. (A dedicated limiter test can set it back locally.)
settings.auth_rate_limit_max = 1_000_000


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
