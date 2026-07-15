"""Seller reviews + product/seller trust + visibility thresholds (M2 slice 4)."""

from __future__ import annotations

from app.core.config import settings
from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_seller(client) -> tuple[str, str]:
    """Register a user and promote to seller via the moderator endpoint."""
    sid, seller_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    resp = client.patch(f"/api/v1/users/{sid}/role", headers=_auth(mod_token),
                        json={"role": "seller"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "seller"
    return sid, seller_token


SELLER_REVIEW = {
    "accuracy": True, "order_completeness": True, "customer_service": 5,
    "packaging_quality": 4, "overall_rating": 5, "would_recommend": True,
}


@requires_db
def test_role_rbac_and_moderator_not_grantable(client):
    uid, user_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")

    # Non-moderator cannot change roles.
    assert client.patch(f"/api/v1/users/{uid}/role", headers=_auth(user_token),
                        json={"role": "seller"}).status_code == 403
    # Moderator cannot grant `moderator` via the API.
    resp = client.patch(f"/api/v1/users/{uid}/role", headers=_auth(mod_token),
                        json={"role": "moderator"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "role_not_grantable"
    # Promote + demote works.
    assert client.patch(f"/api/v1/users/{uid}/role", headers=_auth(mod_token),
                        json={"role": "seller"}).json()["role"] == "seller"
    assert client.patch(f"/api/v1/users/{uid}/role", headers=_auth(mod_token),
                        json={"role": "user"}).json()["role"] == "user"


@requires_db
def test_seller_review_flow_aggregates_and_trust(client):
    seller_id, seller_token, = _make_seller(client)
    _, reviewer_token, _ = register_and_token(client)
    rh = _auth(reviewer_token)

    # Reviewing a non-seller -> 404.
    plain_uid, _, _ = register_and_token(client)
    assert client.post(f"/api/v1/sellers/{plain_uid}/reviews", headers=rh,
                       json=SELLER_REVIEW).status_code == 404

    # Self-review -> 409.
    resp = client.post(f"/api/v1/sellers/{seller_id}/reviews",
                       headers=_auth(seller_token), json=SELLER_REVIEW)
    assert resp.status_code == 409

    # Happy path publishes immediately.
    resp = client.post(f"/api/v1/sellers/{seller_id}/reviews", headers=rh,
                       json=SELLER_REVIEW)
    assert resp.status_code == 201, resp.text

    # Duplicate by the same reviewer -> 409.
    resp = client.post(f"/api/v1/sellers/{seller_id}/reviews", headers=rh,
                       json=SELLER_REVIEW)
    assert resp.status_code == 409
    assert resp.json()["code"] == "seller_review_exists"

    # A second reviewer who would NOT recommend.
    _, reviewer2, _ = register_and_token(client)
    negative = {**SELLER_REVIEW, "accuracy": False, "customer_service": 1,
                "would_recommend": False, "overall_rating": 1}
    assert client.post(f"/api/v1/sellers/{seller_id}/reviews",
                       headers=_auth(reviewer2), json=negative).status_code == 201

    profile = client.get(f"/api/v1/sellers/{seller_id}").json()
    assert profile["review_count"] == 2
    assert profile["accuracy_pct"] == 50.0
    assert profile["recommend_pct"] == 50.0
    assert profile["customer_service_avg"] == 3.0
    trust_2 = float(profile["seller_trust_score"])
    assert 0 < trust_2 < 1

    # More recommends move seller trust up.
    for _ in range(3):
        _, tok, _ = register_and_token(client)
        assert client.post(f"/api/v1/sellers/{seller_id}/reviews",
                           headers=_auth(tok), json=SELLER_REVIEW).status_code == 201
    profile = client.get(f"/api/v1/sellers/{seller_id}").json()
    assert float(profile["seller_trust_score"]) > trust_2

    # Listing endpoint, newest first.
    listed = client.get(f"/api/v1/sellers/{seller_id}/reviews").json()
    assert len(listed) == 5


@requires_db
def test_product_trust_and_visibility_threshold(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    # 5-star published review -> positive product trust.
    good_rid, good_pid = make_published_review(client, ah, mh, stars=5,
                                               name="GoodTrustWidget")
    good = client.get(f"/api/v1/products/{good_pid}").json()
    assert float(good["trust_score"]) > 0
    assert good["low_trust"] is False

    # 2-star review -> zero trust (no star>=4 votes).
    _, bad_pid = make_published_review(client, ah, mh, stars=2,
                                       name="BadTrustWidget")
    bad = client.get(f"/api/v1/products/{bad_pid}").json()
    assert float(bad["trust_score"]) == 0

    # Threshold ON: only kicks in at min_reviews.
    old = (settings.product_trust_visibility_threshold, settings.product_trust_min_reviews)
    settings.product_trust_visibility_threshold = 0.01
    settings.product_trust_min_reviews = 1
    try:
        listing = [p["id"] for p in client.get("/api/v1/products?limit=200").json()]
        assert bad_pid not in listing          # low trust + enough reviews -> hidden
        assert good_pid in listing
        # Still fetchable by id, flagged.
        assert client.get(f"/api/v1/products/{bad_pid}").json()["low_trust"] is True
        # include_low_trust shows everything.
        listing = [p["id"] for p in
                   client.get("/api/v1/products?limit=200&include_low_trust=true").json()]
        assert bad_pid in listing
        # Below min_reviews the filter must NOT kick in.
        settings.product_trust_min_reviews = 5
        listing = [p["id"] for p in client.get("/api/v1/products?limit=200").json()]
        assert bad_pid in listing
    finally:
        (settings.product_trust_visibility_threshold,
         settings.product_trust_min_reviews) = old
