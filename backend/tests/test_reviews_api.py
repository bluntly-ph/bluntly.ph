"""Review submission, version history, and ownership enforcement (integration)."""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_review_submission_and_versioning(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)

    prod = client.post("/api/v1/products", headers=headers,
                       json={"name": "Test Earbuds", "category": "electronics"})
    assert prod.status_code == 201, prod.text
    product_id = prod.json()["id"]

    created = client.post("/api/v1/reviews", headers=headers, json={
        "product_id": product_id, "title": "Solid pick", "discussion": "Used daily for a month.",
        "verdict": "yes_absolutely", "star_rating": 4, "pros": ["battery"], "cons": ["case"],
        "photo_url": "https://example.com/proof.jpg"})
    assert created.status_code == 201, created.text
    review = created.json()
    review_id = review["id"]
    assert review["verification_status"] == "verified"  # photo => verified
    assert review["current_version"] == 1
    # Publication gate: hidden + auto-queued on submit.
    assert review["published_at"] is None
    assert review["earn_eligible_status"] == "pending"
    assert review["referral_redirect_url"] is None

    # Edit creates version 2.
    edited = client.patch(f"/api/v1/reviews/{review_id}", headers=headers,
                          json={"title": "Solid pick (updated)", "change_note": "clarified title"})
    assert edited.status_code == 200
    assert edited.json()["current_version"] == 2
    assert edited.json()["title"] == "Solid pick (updated)"

    # No-op edit does not bump the version.
    noop = client.patch(f"/api/v1/reviews/{review_id}", headers=headers,
                        json={"title": "Solid pick (updated)"})
    assert noop.json()["current_version"] == 2

    # Versions of an unpublished review require the author's (or a mod's) auth.
    assert client.get(f"/api/v1/reviews/{review_id}/versions").status_code == 404
    versions = client.get(f"/api/v1/reviews/{review_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert [v["version_number"] for v in versions.json()] == [1, 2]

    v1 = client.get(f"/api/v1/reviews/{review_id}/versions/1", headers=headers)
    assert v1.json()["snapshot"]["title"] == "Solid pick"  # original preserved


@requires_db
def test_unverified_without_photo(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product_id = client.post("/api/v1/products", headers=headers,
                             json={"name": "No Photo Product"}).json()["id"]
    r = client.post("/api/v1/reviews", headers=headers, json={
        "product_id": product_id, "title": "Meh", "discussion": "No proof attached.",
        "verdict": "it_depends", "star_rating": 3})
    assert r.json()["verification_status"] == "unverified"


@requires_db
def test_only_author_or_moderator_can_edit(client):
    _, author_token, _ = register_and_token(client)
    _, other_token, _ = register_and_token(client)
    ah = _auth(author_token)

    product_id = client.post("/api/v1/products", headers=ah,
                             json={"name": "Owned Product"}).json()["id"]
    review_id = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": product_id, "title": "Mine", "discussion": "My review.",
        "verdict": "hard_pass", "star_rating": 2}).json()["id"]

    forbidden = client.patch(f"/api/v1/reviews/{review_id}", headers=_auth(other_token),
                             json={"title": "hijack"})
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "not_review_owner"

    # A moderator may edit.
    _, mod_token, _ = register_and_token(client, role="moderator")
    ok = client.patch(f"/api/v1/reviews/{review_id}", headers=_auth(mod_token),
                      json={"title": "moderated", "change_note": "policy edit"})
    assert ok.status_code == 200
    assert ok.json()["current_version"] == 2
