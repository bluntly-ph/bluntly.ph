"""Referral link flow (M2 slice 1) — publication gate, attach/publish/reject/revoke,
attribution redirect, RBAC (integration)."""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db

SHOPEE_URL = "https://shopee.ph/product/abc-i.123.456"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_review(client, headers, *, stars: int = 4, photo: bool = True,
                 name: str = "Widget") -> tuple[str, str]:
    pid = client.post("/api/v1/products", headers=headers,
                      json={"name": name, "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Great", "discussion": "Used it for weeks; solid.",
            "verdict": "yes_absolutely", "star_rating": stars}
    if photo:
        body["photo_url"] = "https://example.com/proof.jpg"
    rid = client.post("/api/v1/reviews", headers=headers, json=body).json()["id"]
    return rid, pid


@requires_db
def test_full_referral_flow(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    rid, _ = _make_review(client, ah, stars=4)

    # Hidden from the public list, visible to the author.
    anon_ids = [r["id"] for r in client.get("/api/v1/reviews").json()]
    assert rid not in anon_ids
    own_ids = [r["id"] for r in client.get("/api/v1/reviews", headers=ah).json()]
    assert rid in own_ids
    # Anonymous GET of the unpublished review → 404.
    assert client.get(f"/api/v1/reviews/{rid}").status_code == 404

    # In the moderator queue.
    queue = client.get("/api/v1/admin/review-queue", headers=mh).json()
    assert rid in [item["review"]["id"] for item in queue["pending"]]
    # Non-moderator is forbidden.
    assert client.get("/api/v1/admin/review-queue", headers=ah).status_code == 403

    # Paste link → monetized + published (one action).
    attach = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                         json={"url": SHOPEE_URL, "platform": "shopee"})
    assert attach.status_code == 200, attach.text
    body = attach.json()
    assert body["earn_eligible_status"] == "monetized"
    assert body["published_at"] is not None
    assert body["referral_redirect_url"] == f"/r/{rid}"
    # Raw affiliate URL must NOT be exposed.
    assert "affiliate_link" not in body and SHOPEE_URL not in str(body)

    # Now public.
    assert rid in [r["id"] for r in client.get("/api/v1/reviews").json()]

    # Attribution redirect → 302 to the affiliate URL + a click session row.
    from app.db.session import SessionLocal
    from app.models.session import Session as ClickSession
    resp = client.get(f"/r/{rid}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == SHOPEE_URL
    db = SessionLocal()
    try:
        import uuid as _uuid

        from sqlalchemy import func, select
        n = db.scalar(select(func.count(ClickSession.id)).where(
            ClickSession.review_id == _uuid.UUID(rid)))
        assert n == 1
    finally:
        db.close()

    # Revoke → stays published, drops to approved, redirect 404s.
    rev = client.request("DELETE", f"/api/v1/admin/reviews/{rid}/referral-link",
                         headers=mh, json={"reason": "expired link"})
    assert rev.status_code == 200
    assert rev.json()["earn_eligible_status"] == "approved"
    assert rev.json()["published_at"] is not None       # still live
    assert client.get(f"/r/{rid}", follow_redirects=False).status_code == 404

    # Re-attach works.
    again = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                        json={"url": SHOPEE_URL, "platform": "shopee"})
    assert again.status_code == 200
    assert again.json()["earn_eligible_status"] == "monetized"

    # History shows revoked + active.
    hist = client.get(f"/api/v1/admin/reviews/{rid}/referral-links", headers=mh).json()
    statuses = sorted(link["status"] for link in hist)
    assert statuses == ["active", "revoked"]


@requires_db
def test_low_star_publishes_without_link(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, _auth(author_token), stars=2)

    # Attaching a link to a <=2* review is refused.
    bad = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                      json={"url": SHOPEE_URL, "platform": "shopee"})
    assert bad.status_code == 409 and bad.json()["code"] == "stars_too_low_for_link"

    # Publish without a link → Honesty Fund, live.
    pub = client.post(f"/api/v1/admin/reviews/{rid}/publish", headers=mh)
    assert pub.status_code == 200
    assert pub.json()["earn_eligible_status"] == "honesty_fund"
    assert pub.json()["published_at"] is not None


@requires_db
def test_reject_then_edit_requeues(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    rid, _ = _make_review(client, ah, stars=5)

    rej = client.post(f"/api/v1/admin/reviews/{rid}/reject", headers=_auth(mod_token),
                      json={"reason": "needs a clearer proof photo"})
    assert rej.status_code == 200
    assert rej.json()["earn_eligible_status"] == "rejected"
    assert rej.json()["published_at"] is None

    edited = client.patch(f"/api/v1/reviews/{rid}", headers=ah,
                          json={"discussion": "Reworded with more detail.", "change_note": "fix"})
    assert edited.json()["earn_eligible_status"] == "pending"  # re-queued


@requires_db
def test_unverified_cannot_be_monetized(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    rid, _ = _make_review(client, _auth(author_token), stars=4, photo=False)  # unverified
    r = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=_auth(mod_token),
                    json={"url": SHOPEE_URL, "platform": "shopee"})
    assert r.status_code == 409 and r.json()["code"] == "review_not_verified"


@requires_db
def test_url_validation_via_attach(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, _auth(author_token), stars=4)

    # Wrong platform for a valid shopee URL.
    r1 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": SHOPEE_URL, "platform": "amazon"})
    assert r1.status_code == 422 and r1.json()["code"] == "affiliate_url_invalid"
    # http (not https).
    r2 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": "http://shopee.ph/x", "platform": "shopee"})
    assert r2.status_code == 422
    # Unrelated domain.
    r3 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": "https://evil.example.com/x", "platform": "shopee"})
    assert r3.status_code == 422


@requires_db
def test_admin_routes_require_moderator(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    rid, _ = _make_review(client, ah, stars=4)
    link_body = {"url": SHOPEE_URL, "platform": "shopee"}
    for method, path, body in [
        ("post", f"/api/v1/admin/reviews/{rid}/referral-link", link_body),
        ("post", f"/api/v1/admin/reviews/{rid}/publish", None),
        ("post", f"/api/v1/admin/reviews/{rid}/reject", {"reason": "x"}),
        ("post", f"/api/v1/admin/reviews/{rid}/unpublish", {}),
    ]:
        resp = client.request(method, path, headers=ah, json=body)
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


@requires_db
def test_edited_since_monetized_flag(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, ah, stars=4)
    client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                json={"url": SHOPEE_URL, "platform": "shopee"})
    # Author edits after monetization → version bumps past the link's snapshot.
    client.patch(f"/api/v1/reviews/{rid}", headers=ah,
                 json={"title": "Great (revised)", "change_note": "typo"})
    queue = client.get("/api/v1/admin/review-queue", headers=mh).json()
    assert rid in [item["review"]["id"] for item in queue["edited_since_monetized"]]
