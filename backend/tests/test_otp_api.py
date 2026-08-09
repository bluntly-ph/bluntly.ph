"""OTP endpoints — contract, signup privacy, and login onboarding handoff."""

from __future__ import annotations

import uuid

from app.services import otp_service
from tests.conftest import requires_db

BASE = "/api/v1/auth"


def _fresh_email() -> str:
    return f"otpapi-{uuid.uuid4().hex[:12]}@example.com"


@requires_db
def test_login_unknown_address_returns_signup_prompt_problem(client):
    r = client.post(f"{BASE}/otp/request",
                    json={"email": _fresh_email(), "purpose": "login"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "account_not_found"


@requires_db
def test_signup_round_trip_returns_token(client, monkeypatch):
    sent: dict[str, str] = {}
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


@requires_db
def test_malformed_code_is_a_validation_error(client):
    r = client.post(f"{BASE}/otp/verify",
                    json={"email": _fresh_email(), "code": "abc"})
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"
