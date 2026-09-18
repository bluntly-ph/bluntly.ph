"""The author's own reviews in every state — GET /reviews/mine (2026-09-18).

A real user submitted a review, saw it accepted, refreshed their profile and
found it gone. It was not gone: every review is held for moderation, and the
profile read the public feed, which is publication-gated by design. These pin
the contract the profile now reads instead:

    pending    visible to its author as pending; nowhere public
    published  visible to its author and publicly
    rejected   visible to its author with the reason; nowhere public

and that the public gate is unchanged for everyone else.
"""

from __future__ import annotations

import uuid

from tests.conftest import owned_photo_url, register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _product(client, headers: dict) -> str:
    resp = client.post("/api/v1/products", headers=headers,
                       json={"name": f"OwnReviewsWidget {uuid.uuid4().hex[:8]}",
                             "category": "electronics"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _submit(client, headers: dict, product_id: str, title: str) -> dict:
    resp = client.post("/api/v1/reviews", headers=headers, json={
        "product_id": product_id,
        "title": title,
        "discussion": "Weeks of use and it has held up well.",
        "verdict": "yes_absolutely",
        "star_rating": 4,
        "photo_url": owned_photo_url(headers),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _mine(client, headers: dict) -> dict[str, dict]:
    resp = client.get("/api/v1/reviews/mine", headers=headers, params={"limit": 100})
    assert resp.status_code == 200, resp.text
    return {item["review"]["id"]: item for item in resp.json()}


def _public_feed_ids(client, author_id: str, headers: dict | None = None) -> set[str]:
    resp = client.get("/api/v1/reviews/feed", headers=headers or {},
                      params={"author_id": author_id, "sort": "newest", "limit": 100})
    assert resp.status_code == 200, resp.text
    return {item["review"]["id"] for item in resp.json()}


@requires_db
def test_mine_needs_a_signed_in_caller(client):
    assert client.get("/api/v1/reviews/mine").status_code == 401


@requires_db
def test_a_submitted_review_stays_with_its_author_as_pending_and_nowhere_public(client):
    author_id, token, _ = register_and_token(client)
    headers = _auth(token)
    review = _submit(client, headers, _product(client, headers), "Held for moderation")

    # Exactly one row, and it is waiting for a moderator.
    assert review["published_at"] is None
    mine = _mine(client, headers)
    assert review["id"] in mine
    item = mine[review["id"]]
    assert item["status"] == "pending"
    assert item["rejection_reason"] is None
    assert item["product"] is not None and item["author"]["id"] == str(author_id)
    # A second read is the "hard refresh": still there.
    assert review["id"] in _mine(client, headers)

    # The author can open it; nobody else can see it anywhere.
    assert client.get(f"/api/v1/reviews/{review['id']}/full", headers=headers).status_code == 200
    assert client.get(f"/api/v1/reviews/{review['id']}/full").status_code == 404
    _, other_token, _ = register_and_token(client)
    other = _auth(other_token)
    assert client.get(f"/api/v1/reviews/{review['id']}/full", headers=other).status_code == 404
    assert review["id"] not in _mine(client, other)
    assert review["id"] not in _public_feed_ids(client, str(author_id))
    assert review["id"] not in _public_feed_ids(client, str(author_id), other)


@requires_db
def test_a_moderator_sees_it_and_publishing_makes_it_public(client):
    author_id, token, _ = register_and_token(client)
    headers = _auth(token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    review = _submit(client, headers, _product(client, headers), "Worth publishing")

    held = client.get(f"/api/v1/reviews/{review['id']}/full", headers=_auth(mod_token))
    assert held.status_code == 200, held.text

    published = client.post(f"/api/v1/admin/reviews/{review['id']}/publish",
                            headers=_auth(mod_token))
    assert published.status_code == 200, published.text

    assert _mine(client, headers)[review["id"]]["status"] == "published"
    assert review["id"] in _public_feed_ids(client, str(author_id))
    assert client.get(f"/api/v1/reviews/{review['id']}/full").status_code == 200


@requires_db
def test_a_rejected_review_tells_its_author_why_and_stays_private(client):
    author_id, token, _ = register_and_token(client)
    headers = _auth(token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    review = _submit(client, headers, _product(client, headers), "Not this one")

    rejected = client.post(f"/api/v1/admin/reviews/{review['id']}/reject",
                           headers=_auth(mod_token), json={"reason": "No proof of purchase."})
    assert rejected.status_code == 200, rejected.text

    item = _mine(client, headers)[review["id"]]
    assert item["status"] == "rejected"
    assert item["rejection_reason"] == "No proof of purchase."
    assert review["id"] not in _public_feed_ids(client, str(author_id))
    assert client.get(f"/api/v1/reviews/{review['id']}/full").status_code == 404


@requires_db
def test_mine_is_the_callers_own_newest_first(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product = _product(client, headers)
    first = _submit(client, headers, product, "First of two")
    second = _submit(client, headers, product, "Second of two")

    resp = client.get("/api/v1/reviews/mine", headers=headers, params={"limit": 100})
    ids = [item["review"]["id"] for item in resp.json()]
    assert ids.index(second["id"]) < ids.index(first["id"])
    # There is no author parameter to point it at someone else.
    _, other_token, _ = register_and_token(client)
    assert client.get("/api/v1/reviews/mine", headers=_auth(other_token),
                      params={"author_id": ids[0]}).json() == []
