"""Token economy (M2 slice 7) — ledger, hooks, admin grants."""

from __future__ import annotations

import uuid as _uuid

from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _balance(client, headers) -> int:
    return client.get("/api/v1/tokens/balance", headers=headers).json()["token_balance"]


@requires_db
def test_publish_awards_once_even_after_republish(client):
    from app.core.config import settings

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    assert _balance(client, ah) == 0
    rid, _ = make_published_review(client, ah, mh, name=f"TokenWidget-{_uuid.uuid4().hex[:6]}")
    assert _balance(client, ah) == settings.tokens_on_review_published

    # Unpublish -> republish must NOT double-award (uq_token_once).
    assert client.post(f"/api/v1/admin/reviews/{rid}/unpublish", headers=mh,
                       json={"reason": "check"}).status_code == 200
    assert client.post(f"/api/v1/admin/reviews/{rid}/publish",
                       headers=mh).status_code == 200
    assert _balance(client, ah) == settings.tokens_on_review_published

    # Ledger shows exactly one earn row for this review.
    txs = client.get("/api/v1/tokens/transactions", headers=ah).json()
    earns = [t for t in txs if t["kind"] == "earn_review_published"
             and t["ref_id"] == rid]
    assert len(earns) == 1


@requires_db
def test_admin_grant_deduct_and_ledger_chain(client):
    uid, user_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    uh, mh = _auth(user_token), _auth(mod_token)

    # Non-moderator cannot grant.
    assert client.post(f"/api/v1/admin/users/{uid}/tokens", headers=uh,
                       json={"amount": 5, "note": "nope"}).status_code == 403
    # Zero amount rejected.
    assert client.post(f"/api/v1/admin/users/{uid}/tokens", headers=mh,
                       json={"amount": 0, "note": "zero"}).status_code == 422

    grant = client.post(f"/api/v1/admin/users/{uid}/tokens", headers=mh,
                        json={"amount": 50, "note": "welcome bonus"}).json()
    assert grant["kind"] == "admin_grant" and grant["balance_after"] == 50
    deduct = client.post(f"/api/v1/admin/users/{uid}/tokens", headers=mh,
                         json={"amount": -20, "note": "correction"}).json()
    assert deduct["kind"] == "admin_deduct" and deduct["balance_after"] == 30
    assert _balance(client, uh) == 30

    # Deduct below zero -> 409, balance untouched.
    resp = client.post(f"/api/v1/admin/users/{uid}/tokens", headers=mh,
                       json={"amount": -31, "note": "too much"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "insufficient_tokens"
    assert _balance(client, uh) == 30

    # balance_after chain is consistent (newest first).
    txs = client.get("/api/v1/tokens/transactions", headers=uh).json()
    assert [t["balance_after"] for t in txs] == [30, 50]
    assert [t["amount"] for t in txs] == [-20, 50]

    # Transactions are own-only: another user sees an empty ledger, and there is
    # no cross-user path (endpoint takes no user id).
    _, other_token, _ = register_and_token(client)
    assert client.get("/api/v1/tokens/transactions", headers=_auth(other_token)).json() == []


@requires_db
def test_commission_award_idempotent(client):
    """Import the same commission file twice: tokens award exactly once."""
    from app.core.config import settings
    from tests.test_commissions_api import (
        HEADER,
        _import,
        ensure_tier_configs,
        make_click,
    )

    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    tokens_before = _balance(client, ah)
    _, click_ref, _ = make_click(client, ah, mh,
                                 name=f"TokCsvWidget-{_uuid.uuid4().hex[:6]}")
    # make_click published a review -> publish tokens land first.
    expected_after_publish = tokens_before + settings.tokens_on_review_published
    assert _balance(client, ah) == expected_after_publish

    csv_text = f"{HEADER}\n{click_ref},,200.00,PHP,completed,shopee\n"
    assert _import(client, mh, csv_text, filename="tok.csv").status_code == 200
    expected = expected_after_publish + settings.tokens_on_commission
    assert _balance(client, ah) == expected

    # Same file again -> duplicate row skipped -> no new tokens.
    assert _import(client, mh, csv_text, filename="tok.csv").status_code == 200
    assert _balance(client, ah) == expected
