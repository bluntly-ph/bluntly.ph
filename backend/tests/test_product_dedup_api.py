"""Duplicate product detection against a real database (FR-2 2.8).

Every name here carries a per-test suffix: the isolated CI database is
cumulative, and a fixed name would now match a previous run's product.
"""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(client, headers: dict, **body):
    return client.post("/api/v1/products", headers=headers,
                       json={"category": "electronics", **body})


@requires_db
def test_the_same_name_typed_differently_is_the_same_product(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    tag = uuid.uuid4().hex[:8]

    first = _create(client, headers, name=f"Dedup Fan {tag} Pro")
    assert first.status_code == 201, first.text
    again = _create(client, headers, name=f"  dedup   FAN-{tag} pro ")
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]


@requires_db
def test_the_same_listing_with_other_tracking_is_the_same_product(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    item = uuid.uuid4().int % 10**9

    first = _create(client, headers, name=f"Listing A {item}",
                    source_url=f"https://shopee.ph/listing-i.1.{item}?sp_atk=one")
    assert first.status_code == 201, first.text
    again = _create(client, headers, name=f"Completely different wording {item}",
                    source_url=f"https://www.shopee.ph/listing-i.1.{item}/?sp_atk=two#reviews")
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]


@requires_db
def test_a_genuinely_different_product_is_created(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    tag = uuid.uuid4().hex[:8]

    first = _create(client, headers, name=f"Distinct Fan {tag}")
    second = _create(client, headers, name=f"Distinct Fan {tag} Pro")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
