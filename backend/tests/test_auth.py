"""Auth: password hashing (unit) + register/login/me flow (integration)."""

from __future__ import annotations

import uuid

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from tests.conftest import requires_db


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    uid = uuid.uuid4()
    token = create_access_token(uid, "moderator")
    claims = decode_token(token)
    assert claims["sub"] == str(uid)
    assert claims["role"] == "moderator"


@requires_db
def test_register_login_me_flow(client):
    email = f"flow_{uuid.uuid4().hex}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "display_name": "Flo"})
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    assert reg.json()["user"]["membership_tier"] == "standard"

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "user"

    # Duplicate email -> 409 problem+json.
    dup = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123"})
    assert dup.status_code == 409
    assert dup.json()["code"] == "email_taken"

    # Login (OAuth2 password form).
    login = client.post("/api/v1/auth/login",
                        data={"username": email, "password": "password123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"

    # Wrong password -> 401.
    bad = client.post("/api/v1/auth/login",
                      data={"username": email, "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"


@requires_db
def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
