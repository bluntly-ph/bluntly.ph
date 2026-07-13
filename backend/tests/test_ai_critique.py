"""AI critique: stub provider (unit) + endpoint (integration, provider=stub)."""

from __future__ import annotations

from app.services.ai_critique import StubProvider, get_provider
from tests.conftest import register_and_token, requires_db


def test_stub_provider_is_deterministic_and_bounded():
    p = StubProvider()
    text = ("This power bank charged my phone three times on one charge. "
            "Pro: fast charging. However the case is bulky and a bit heavy.")
    a = p.critique("Great power bank", text)
    b = p.critique("Great power bank", text)
    assert a == b
    assert 0 <= a.quality_score <= 100
    assert a.provider == "stub"
    assert a.suggestions  # always offers at least one suggestion


def test_get_provider_defaults_to_stub():
    # Settings default AI_PROVIDER=stub in tests (no key configured).
    assert get_provider().name == "stub"


@requires_db
def test_ad_hoc_critique_endpoint(client):
    _, token, _ = register_and_token(client)
    resp = client.post("/api/v1/ai/critique",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"title": "Draft", "text": "Short but honest review with a con: loud."})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider"] == "stub"
    assert 0 <= body["quality_score"] <= 100


@requires_db
def test_critique_requires_auth(client):
    assert client.post("/api/v1/ai/critique", json={"text": "x"}).status_code == 401
