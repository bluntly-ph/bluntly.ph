"""Disclosure of a material relationship, against a real database (X.1)."""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _product(client, headers: dict) -> str:
    resp = client.post("/api/v1/products", headers=headers,
                       json={"name": f"Disclosure {uuid.uuid4().hex[:10]}",
                             "category": "electronics"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _review(product_id: str, **extra) -> dict:
    body = {"product_id": product_id, "title": "Light and quiet",
            "discussion": "Used it daily for a month and it held up fine.",
            "verdict": "it_depends", "star_rating": 4}
    body.update(extra)
    return body


@requires_db
def test_a_declared_relationship_is_stored_with_the_review(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product_id = _product(client, headers)

    resp = client.post("/api/v1/reviews", headers=headers,
                       json=_review(product_id, material_relationship="connected"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["material_relationship"] == "connected"


@requires_db
def test_a_review_that_was_never_asked_says_nothing(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product_id = _product(client, headers)

    resp = client.post("/api/v1/reviews", headers=headers, json=_review(product_id))
    assert resp.status_code == 201, resp.text
    assert resp.json()["material_relationship"] is None


@requires_db
def test_an_unknown_relationship_is_refused(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product_id = _product(client, headers)

    resp = client.post("/api/v1/reviews", headers=headers,
                       json=_review(product_id, material_relationship="paid_promotion"))
    assert resp.status_code == 422
