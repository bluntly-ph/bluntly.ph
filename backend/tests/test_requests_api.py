"""Request board — escrow, rewards, AI validation, fulfilment (M3 slice 9)."""

from __future__ import annotations

import uuid as _uuid

import pytest

from app.core.config import settings
from app.services.ai_critique import heuristic_validate
from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review

GOOD_DETAILS = ("I want an honest look at battery life and build quality after "
                "at least two weeks of daily use, please.")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _balance(client, headers) -> int:
    return client.get("/api/v1/tokens/balance", headers=headers).json()["token_balance"]


def _fund(client, uid: str, mod_headers: dict, amount: int) -> None:
    """Give a user tokens via the admin grant (the only mint path)."""
    r = client.post(f"/api/v1/admin/users/{uid}/tokens", headers=mod_headers,
                    json={"amount": amount, "note": "test funding"})
    assert r.status_code == 200, r.text


# --- pure heuristic contract (no DB) ---
@pytest.mark.parametrize(("title", "details", "src", "valid"), [
    ("Review this fan", GOOD_DETAILS, None, True),
    ("Review this fan", "too short", None, False),                      # < 30 chars
    ("Same text here padded out to thirty plus", "Same text here padded out to thirty plus",
     None, False),                                                      # title == details
    ("Review this", GOOD_DETAILS + " https://evil.example.com/x", None, False),  # foreign link
    ("Review this", GOOD_DETAILS + " https://shopee.ph/x",
     "https://shopee.ph/item", True),                                   # same host as source_url
])
def test_heuristic_validation_contract(title, details, src, valid):
    ok, reasons = heuristic_validate(title, details, src)
    assert ok is valid
    assert ok or reasons  # a rejection always explains itself


@requires_db
def test_create_escrows_and_cancel_refunds(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 100)
    before = _balance(client, h)

    r = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this handheld fan", "details": GOOD_DETAILS, "bounty": 25})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "open"
    assert body["effective_reward"] == 25          # no up-votes yet
    assert body["ai_validation"]["valid"] is True
    assert _balance(client, h) == before - 25      # escrowed

    rid = body["id"]
    cancelled = client.delete(f"/api/v1/requests/{rid}", headers=h)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert _balance(client, h) == before           # refunded exactly

    # Ledger shows the escrow and the refund, and nothing else.
    kinds = [t["kind"] for t in client.get("/api/v1/tokens/transactions",
                                           headers=h).json() if t["ref_id"] == rid]
    assert sorted(kinds) == ["refund_request_escrow", "spend_request_escrow"]


@requires_db
def test_create_guards(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)

    # AI screening rejects thin details with reasons.
    r = client.post("/api/v1/requests", headers=h, json={
        "title": "Review it", "details": "pls", "bounty": 10})
    assert r.status_code == 422
    assert r.json()["code"] == "request_invalid"
    assert r.json()["reasons"]

    # Below the minimum bounty.
    r = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this fan", "details": GOOD_DETAILS,
        "bounty": settings.request_min_bounty - 1})
    assert r.status_code == 422 and r.json()["code"] == "bounty_below_minimum"

    # Can't escrow what you don't have (user has 0 tokens).
    r = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this fan", "details": GOOD_DETAILS, "bounty": 10_000})
    assert r.status_code == 409 and r.json()["code"] == "insufficient_tokens"

    # Anonymous.
    assert client.post("/api/v1/requests", json={
        "title": "x", "details": GOOD_DETAILS, "bounty": 10}).status_code == 401
    _fund(client, uid, mh, 50)  # keep the fixture usable


@requires_db
def test_upvotes_drive_reward_with_cap(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 100)
    rid = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this blender", "details": GOOD_DETAILS, "bounty": 10}).json()["id"]

    # Self-upvote blocked.
    assert client.post(f"/api/v1/requests/{rid}/upvote",
                       headers=h).json()["code"] == "cannot_upvote_own_request"

    _, v1, _ = register_and_token(client)
    r = client.post(f"/api/v1/requests/{rid}/upvote", headers=_auth(v1))
    assert r.status_code == 200
    assert r.json()["upvote_count"] == 1
    assert r.json()["effective_reward"] == 10 + settings.request_topup_per_upvote

    # Same user twice -> 409.
    assert client.post(f"/api/v1/requests/{rid}/upvote",
                       headers=_auth(v1)).status_code == 409
    # Remove own upvote.
    r = client.delete(f"/api/v1/requests/{rid}/upvote", headers=_auth(v1))
    assert r.json()["upvote_count"] == 0 and r.json()["effective_reward"] == 10
    assert client.delete(f"/api/v1/requests/{rid}/upvote",
                         headers=_auth(v1)).status_code == 404

    # Top-up is capped no matter how many up-votes arrive.
    needed = settings.request_topup_cap // settings.request_topup_per_upvote + 3
    for _ in range(needed):
        _, tok, _ = register_and_token(client)
        assert client.post(f"/api/v1/requests/{rid}/upvote",
                           headers=_auth(tok)).status_code == 200
    final = client.get(f"/api/v1/requests/{rid}").json()
    assert final["effective_reward"] == 10 + settings.request_topup_cap


@requires_db
def test_fulfill_guards_and_payout(client):
    req_uid, req_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    rh, mh = _auth(req_token), _auth(mod_token)
    _fund(client, req_uid, mh, 100)

    reviewer_uid, rev_token, _ = register_and_token(client)
    vh = _auth(rev_token)

    rid = client.post("/api/v1/requests", headers=rh, json={
        "title": "Review this kettle", "details": GOOD_DETAILS, "bounty": 20}).json()["id"]
    # One up-vote -> reward 20 + 2
    _, v1, _ = register_and_token(client)
    client.post(f"/api/v1/requests/{rid}/upvote", headers=_auth(v1))

    # An unpublished review cannot fulfill.
    pid = client.post("/api/v1/products", headers=vh,
                      json={"name": f"Kettle-{_uuid.uuid4().hex[:6]}"}).json()["id"]
    draft = client.post("/api/v1/reviews", headers=vh, json={
        "product_id": pid, "title": "Draft", "discussion": "Not yet published.",
        "verdict": "it_depends", "star_rating": 3}).json()["id"]
    r = client.post(f"/api/v1/requests/{rid}/fulfill", headers=vh, json={"review_id": draft})
    assert r.status_code == 409 and r.json()["code"] == "review_not_published"

    # Someone else's review cannot fulfill.
    other_rid, _ = make_published_review(client, rh, mh, name=f"Other-{_uuid.uuid4().hex[:5]}")
    r = client.post(f"/api/v1/requests/{rid}/fulfill", headers=vh,
                    json={"review_id": other_rid})
    assert r.status_code == 409 and r.json()["code"] == "not_review_author"

    # Happy path: reviewer's own published review.
    own_rid, _ = make_published_review(client, vh, mh, name=f"Kettle2-{_uuid.uuid4().hex[:5]}")
    before = _balance(client, vh)
    r = client.post(f"/api/v1/requests/{rid}/fulfill", headers=vh, json={"review_id": own_rid})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "fulfilled"
    assert r.json()["fulfilled_by_review_id"] == own_rid
    assert _balance(client, vh) == before + 20 + settings.request_topup_per_upvote

    # Fulfilled once only.
    assert client.post(f"/api/v1/requests/{rid}/fulfill", headers=vh,
                       json={"review_id": own_rid}).status_code == 409
    # And it can no longer be cancelled.
    assert client.delete(f"/api/v1/requests/{rid}", headers=rh).status_code == 409


@requires_db
def test_product_mismatch_blocks_fulfill(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 100)
    reviewer_uid, rev_token, _ = register_and_token(client)
    vh = _auth(rev_token)

    wanted = client.post("/api/v1/products", headers=h,
                         json={"name": f"Wanted-{_uuid.uuid4().hex[:6]}"}).json()["id"]
    rid = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this exact product", "details": GOOD_DETAILS,
        "bounty": 10, "product_id": wanted}).json()["id"]
    # Published review, but for a DIFFERENT product.
    other, _ = make_published_review(client, vh, mh, name=f"Wrong-{_uuid.uuid4().hex[:5]}")
    r = client.post(f"/api/v1/requests/{rid}/fulfill", headers=vh, json={"review_id": other})
    assert r.status_code == 409 and r.json()["code"] == "product_mismatch"


@requires_db
def test_moderator_remove_refunds_and_rbac(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 60)
    before = _balance(client, h)
    rid = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this lamp", "details": GOOD_DETAILS, "bounty": 15}).json()["id"]
    assert _balance(client, h) == before - 15

    # Non-moderator cannot remove.
    assert client.post(f"/api/v1/admin/requests/{rid}/remove", headers=h,
                       json={"reason": "nope"}).status_code == 403
    r = client.post(f"/api/v1/admin/requests/{rid}/remove", headers=mh,
                    json={"reason": "spam"})
    assert r.status_code == 200 and r.json()["status"] == "removed"
    assert _balance(client, h) == before          # requester made whole
    # Removed requests disappear from the board and 404 by id.
    assert client.get(f"/api/v1/requests/{rid}").status_code == 404
    assert rid not in [x["id"] for x in client.get("/api/v1/requests?limit=100").json()]


@requires_db
def test_expiry_refunds_escrow(client):
    from datetime import UTC, datetime, timedelta

    from app.db.session import SessionLocal
    from app.models.request_board import ReviewRequest
    from app.services.request_service import expire_open_requests

    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 40)
    before = _balance(client, h)
    rid = client.post("/api/v1/requests", headers=h, json={
        "title": "Review this mug", "details": GOOD_DETAILS, "bounty": 12}).json()["id"]
    assert _balance(client, h) == before - 12

    db = SessionLocal()
    try:
        db.get(ReviewRequest, _uuid.UUID(rid)).expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
        assert expire_open_requests(db) >= 1
    finally:
        db.close()

    assert client.get(f"/api/v1/requests/{rid}").json()["status"] == "expired"
    assert _balance(client, h) == before          # refunded on expiry


@requires_db
def test_list_sorting_by_reward(client):
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _fund(client, uid, mh, 200)
    small = client.post("/api/v1/requests", headers=h, json={
        "title": "Small bounty request", "details": GOOD_DETAILS, "bounty": 10}).json()["id"]
    big = client.post("/api/v1/requests", headers=h, json={
        "title": "Big bounty request", "details": GOOD_DETAILS, "bounty": 90}).json()["id"]
    ids = [r["id"] for r in client.get("/api/v1/requests?sort=reward&limit=100").json()]
    assert ids.index(big) < ids.index(small)
