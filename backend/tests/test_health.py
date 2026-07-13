"""Health endpoint contract + OpenAPI publication."""

from __future__ import annotations


def test_health_contract(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"status", "product_id", "version", "timestamp"}
    assert body["status"] == "ok"
    assert body["product_id"] == "bluntly-ph"


def test_openapi_published(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Bluntly.ph API"


def test_protected_route_rejects_anonymous(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    # RFC 9457 problem shape.
    body = resp.json()
    assert body["code"] in {"unauthorized", "http_401"}
    assert body["status"] == 401
