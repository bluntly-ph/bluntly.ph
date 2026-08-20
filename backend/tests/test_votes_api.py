"""Community voting + Wilson ranking (M2 slice 2) — integration."""

from __future__ import annotations

import uuid as _uuid

from sqlalchemy import func, select

from app.services.trust import helpfulness_score
from tests.conftest import owned_photo_url, register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_published_review(client, author_headers, mod_headers, *, stars: int = 4,
                          name: str = "VoteWidget") -> tuple[str, str]:
    """Create a verified review and publish it without a link. Returns (rid, pid)."""
    pid = client.post("/api/v1/products", headers=author_headers,
                      json={"name": name, "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Solid", "discussion": f"Weeks of use; {name}.",
            "verdict": "yes_absolutely", "star_rating": stars,
            "photo_url": owned_photo_url(author_headers)}
    rid = client.post("/api/v1/reviews", headers=author_headers, json=body).json()["id"]
    resp = client.post(f"/api/v1/admin/reviews/{rid}/publish", headers=mod_headers)
    assert resp.status_code == 200, resp.text
    return rid, pid


@requires_db
def test_vote_guards(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, voter_token, _ = register_and_token(client)
    ah, mh, vh = _auth(author_token), _auth(mod_token), _auth(voter_token)

    rid, pid = make_published_review(client, ah, mh)

    # Anonymous vote -> 401.
    assert client.post(f"/api/v1/reviews/{rid}/vote", json={"vote": "up"}).status_code == 401
    # Self-vote -> 409 with the pinned code.
    resp = client.post(f"/api/v1/reviews/{rid}/vote", headers=ah, json={"vote": "up"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "cannot_vote_own_review"

    # Vote on an unpublished review -> 404.
    body = {"product_id": pid, "title": "Draft", "discussion": "Unpublished draft.",
            "verdict": "it_depends", "star_rating": 3}
    draft = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]
    resp = client.post(f"/api/v1/reviews/{draft}/vote", headers=vh, json={"vote": "up"})
    assert resp.status_code == 404

    # Removing a vote that doesn't exist -> 404 vote_not_found.
    resp = client.delete(f"/api/v1/reviews/{rid}/vote", headers=vh)
    assert resp.status_code == 404
    assert resp.json()["code"] == "vote_not_found"


@requires_db
def test_vote_upsert_delete_and_counters(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, voter_token, _ = register_and_token(client)
    ah, mh, vh = _auth(author_token), _auth(mod_token), _auth(voter_token)
    rid, _ = make_published_review(client, ah, mh, name="UpsertWidget")

    up = client.post(f"/api/v1/reviews/{rid}/vote", headers=vh, json={"vote": "up"}).json()
    assert (up["helpful_votes"], up["unhelpful_votes"]) == (1, 0)
    assert float(up["wilson_score"]) > 0

    # Regression (autoflush=False): the author's helpfulness must reflect this
    # FIRST vote in the same transaction, not lag one vote behind. Post-ADR-014
    # a lone up-vote scores its Wilson lower bound (20.65), not 100.
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]
    trust = client.get(f"/api/v1/users/{author_id}/trust").json()
    assert float(trust["helpfulness_ratio"]) == helpfulness_score(1, 0)

    # Change direction — upsert, not a second row.
    down = client.post(f"/api/v1/reviews/{rid}/vote", headers=vh, json={"vote": "down"}).json()
    assert (down["helpful_votes"], down["unhelpful_votes"]) == (0, 1)

    from app.db.session import SessionLocal
    from app.models.vote import ReviewVote
    db = SessionLocal()
    try:
        n = db.scalar(select(func.count(ReviewVote.id)).where(
            ReviewVote.review_id == _uuid.UUID(rid)))
        assert n == 1  # unique (review, voter) held
    finally:
        db.close()

    removed = client.delete(f"/api/v1/reviews/{rid}/vote", headers=vh).json()
    assert (removed["helpful_votes"], removed["unhelpful_votes"]) == (0, 0)
    assert float(removed["wilson_score"]) == 0


@requires_db
def test_wilson_sort_and_author_helpfulness(client):
    _, author_token, _ = register_and_token(client)
    author_id = None
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]

    # Two published reviews on the SAME product; one gets 3 up-votes.
    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": "SortWidget", "category": "electronics"}).json()["id"]

    def make(title: str) -> str:
        body = {"product_id": pid, "title": title, "discussion": f"Story of {title}.",
                "verdict": "yes_absolutely", "star_rating": 4,
                "photo_url": owned_photo_url(ah)}
        rid = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]
        assert client.post(f"/api/v1/admin/reviews/{rid}/publish",
                           headers=mh).status_code == 200
        return rid

    plain = make("Plain")
    popular = make("Popular")
    for _ in range(3):
        _, tok, _ = register_and_token(client)
        resp = client.post(f"/api/v1/reviews/{popular}/vote",
                           headers=_auth(tok), json={"vote": "up"})
        assert resp.status_code == 200, resp.text

    listed = client.get(f"/api/v1/reviews?product_id={pid}&sort=wilson").json()
    ids = [r["id"] for r in listed]
    assert ids.index(popular) < ids.index(plain)

    # Author helpfulness: 3 helpful / 0 unhelpful -> Wilson lower bound (ADR-014),
    # which discounts the small sample rather than scoring it a perfect 100.
    trust = client.get(f"/api/v1/users/{author_id}/trust").json()
    assert float(trust["helpfulness_ratio"]) == helpfulness_score(3, 0)
    assert float(trust["helpfulness_ratio"]) < 100.0
