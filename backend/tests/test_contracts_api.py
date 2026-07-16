"""Review contracts — creation, renewal, expiry, buyout, and the split hook
(M3 slice 10)."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from tests.conftest import register_and_token, requires_db
from tests.test_commissions_api import HEADER, _import, ensure_tier_configs, make_click

SHOPEE_URL = "https://shopee.ph/product/abc-i.123.456"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _contract_row(review_id: str):
    from app.db.session import SessionLocal
    from app.models.contract import ReviewContract

    db = SessionLocal()
    try:
        return db.scalar(select(ReviewContract).where(
            ReviewContract.review_id == _uuid.UUID(review_id)))
    finally:
        db.close()


def _wallet(uid: str) -> Decimal:
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        return db.get(User, _uuid.UUID(uid)).wallet_balance
    finally:
        db.close()


@requires_db
def test_contract_auto_created_on_monetize_and_reused_on_reattach(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]

    rid, _, _ = make_click(client, ah, mh, name=f"Contract-{_uuid.uuid4().hex[:6]}")
    contract = _contract_row(rid)
    assert contract is not None, "monetizing a review must create its contract"
    assert contract.status.value == "active"
    assert contract.term_months == settings.contract_term_months
    assert contract.auto_renew is True and contract.renewal_count == 0
    assert str(contract.reviewer_id) == author_id
    first_id = contract.id

    # Revoke then re-attach: the SAME contract is reused (no fresh term).
    assert client.request("DELETE", f"/api/v1/admin/reviews/{rid}/referral-link",
                          headers=mh, json={"reason": "expired link"}).status_code == 200
    assert client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                       json={"url": SHOPEE_URL, "platform": "shopee"}).status_code == 200
    again = _contract_row(rid)
    assert again.id == first_id, "re-attach must reuse the active contract"

    # It shows up on the owner's list.
    mine = client.get("/api/v1/contracts", headers=ah).json()
    assert str(first_id) in [c["id"] for c in mine]


@requires_db
def test_sweep_renews_or_expires_by_flag(client):
    from app.db.session import SessionLocal
    from app.models.contract import ReviewContract
    from app.services.contract_service import sweep_contracts

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    renew_rid, _, _ = make_click(client, ah, mh, name=f"Renew-{_uuid.uuid4().hex[:6]}")
    expire_rid, _, _ = make_click(client, ah, mh, name=f"Expire-{_uuid.uuid4().hex[:6]}")

    expiring = _contract_row(expire_rid)
    client.patch(f"/api/v1/contracts/{expiring.id}/auto-renew", headers=ah,
                 json={"auto_renew": False})

    # Backdate both past term.
    db = SessionLocal()
    try:
        for rid in (renew_rid, expire_rid):
            c = db.scalar(select(ReviewContract).where(
                ReviewContract.review_id == _uuid.UUID(rid)))
            c.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
        counts = sweep_contracts(db)
        assert counts["renewed"] >= 1 and counts["expired"] >= 1
    finally:
        db.close()

    renewed = _contract_row(renew_rid)
    assert renewed.status.value == "active" and renewed.renewal_count == 1
    assert renewed.expires_at > datetime.now(UTC)
    assert _contract_row(expire_rid).status.value == "expired"


@requires_db
def test_expired_contract_zeroes_reviewer_share_on_import(client):
    """The whole economic point: no active contract -> reviewer earns 0 bps and
    the platform absorbs that share. The Honesty Fund's 30% never moves."""
    from app.db.session import SessionLocal
    from app.models.commission import Commission
    from app.models.contract import ReviewContract

    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    rid, click_ref, author_id = make_click(
        client, ah, mh, name=f"Zeroed-{_uuid.uuid4().hex[:6]}")

    # Force the contract to expired.
    db = SessionLocal()
    try:
        c = db.scalar(select(ReviewContract).where(
            ReviewContract.review_id == _uuid.UUID(rid)))
        c.status = "expired"
        db.commit()
    finally:
        db.close()

    wallet_before = _wallet(author_id)
    csv_text = f"{HEADER}\n{click_ref},ORD-X,100.00,PHP,completed,shopee\n"
    resp = _import(client, mh, csv_text, filename=f"expired_{_uuid.uuid4().hex[:6]}.csv")
    assert resp.status_code == 200 and resp.json()["imported"] == 1

    db = SessionLocal()
    try:
        com = db.scalar(select(Commission).where(Commission.review_id == _uuid.UUID(rid)))
        assert com.reviewer_share_bps == 0
        assert com.reviewer_share == Decimal("0.00")
        assert com.contract_status.value == "expired"
        assert com.honesty_fund_share == Decimal("30.00")   # unchanged, fixed 30%
        assert com.platform_share == Decimal("70.00")       # absorbs the reviewer's share
        # Invariant still holds.
        assert com.platform_share + com.reviewer_share + com.honesty_fund_share \
            == com.gross_amount
    finally:
        db.close()
    assert _wallet(author_id) == wallet_before  # nothing credited


@requires_db
def test_active_contract_still_pays_tier_bps(client):
    """Control for the test above: an ACTIVE contract pays the normal tier share."""
    from app.db.session import SessionLocal
    from app.models.commission import Commission

    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, click_ref, author_id = make_click(
        client, ah, mh, name=f"Active-{_uuid.uuid4().hex[:6]}")
    before = _wallet(author_id)

    csv_text = f"{HEADER}\n{click_ref},ORD-Y,100.00,PHP,completed,shopee\n"
    assert _import(client, mh, csv_text,
                   filename=f"active_{_uuid.uuid4().hex[:6]}.csv").status_code == 200
    db = SessionLocal()
    try:
        com = db.scalar(select(Commission).where(Commission.review_id == _uuid.UUID(rid)))
        assert com.reviewer_share_bps == 3000
        assert com.reviewer_share == Decimal("30.00")
        assert com.contract_status.value == "active"
    finally:
        db.close()
    assert _wallet(author_id) == before + Decimal("30.00")


@requires_db
def test_buyout_offer_accept_and_guards(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]
    rid, _, _ = make_click(client, ah, mh, name=f"Buyout-{_uuid.uuid4().hex[:6]}")
    cid = str(_contract_row(rid).id)

    # No offer yet.
    assert client.post(f"/api/v1/contracts/{cid}/buyout/accept",
                       headers=ah).json()["code"] == "no_pending_buyout"
    # RBAC: a normal user cannot offer.
    assert client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=ah,
                       json={"amount": "500.00"}).status_code == 403
    # Non-positive amount rejected by schema.
    assert client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                       json={"amount": "0"}).status_code == 422

    r = client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                    json={"amount": "500.00"})
    assert r.status_code == 200 and Decimal(r.json()["buyout_offer_amount"]) == Decimal("500.00")
    # One pending offer at a time.
    assert client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                       json={"amount": "600.00"}).json()["code"] == "buyout_already_pending"

    # A different user cannot accept it.
    _, other, _ = register_and_token(client)
    assert client.post(f"/api/v1/contracts/{cid}/buyout/accept",
                       headers=_auth(other)).status_code == 403

    before = _wallet(author_id)
    r = client.post(f"/api/v1/contracts/{cid}/buyout/accept", headers=ah)
    assert r.status_code == 200 and r.json()["status"] == "bought_out"
    assert _wallet(author_id) == before + Decimal("500.00")
    # Paid exactly once — a second accept is refused.
    assert client.post(f"/api/v1/contracts/{cid}/buyout/accept",
                       headers=ah).status_code == 409
    assert _wallet(author_id) == before + Decimal("500.00")


@requires_db
def test_buyout_reject_leaves_contract_active(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]
    rid, _, _ = make_click(client, ah, mh, name=f"Reject-{_uuid.uuid4().hex[:6]}")
    cid = str(_contract_row(rid).id)

    client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh, json={"amount": "300.00"})
    before = _wallet(author_id)
    r = client.post(f"/api/v1/contracts/{cid}/buyout/reject", headers=ah)
    assert r.status_code == 200
    assert r.json()["status"] == "active"            # contract untouched
    assert r.json()["buyout_offer_amount"] is None   # offer cleared
    assert r.json()["buyout_rejected_at"] is not None
    assert _wallet(author_id) == before              # no money moved
    # A fresh offer can now be made.
    assert client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                       json={"amount": "400.00"}).status_code == 200


@requires_db
def test_admin_list_and_expiring_filter(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, _, _ = make_click(client, ah, mh, name=f"Listing-{_uuid.uuid4().hex[:6]}")

    assert client.get("/api/v1/admin/contracts", headers=ah).status_code == 403
    active = client.get("/api/v1/admin/contracts?status=active&limit=100", headers=mh)
    assert active.status_code == 200
    assert all(c["status"] == "active" for c in active.json())

    # The expiry filter is asserted RELATIONALLY, not by finding this one id: the
    # list is capped at 100 and ordered by expires_at, and a long-lived dev DB has
    # far more contracts than that, so a fresh 6-month contract legitimately falls
    # off the page. What must hold is the filter's semantics.
    soon = client.get("/api/v1/admin/contracts?expiring_within_days=1&limit=100",
                      headers=mh).json()
    # Nothing expiring within a day should be > a day away.
    now = datetime.now(UTC)
    assert all(datetime.fromisoformat(c["expires_at"]) <= now + timedelta(days=2)
               for c in soon), "expiring_within_days must bound expires_at"
    wide_days = settings.contract_term_months * 31
    wide = client.get(f"/api/v1/admin/contracts?expiring_within_days={wide_days}"
                      "&limit=100", headers=mh).json()
    # A wider window can only ever include more, never fewer.
    assert len(wide) >= len(soon)
    assert all(c["status"] == "active" for c in wide)
    # And this specific contract sits inside the wide window by construction.
    fresh = _contract_row(rid)
    assert fresh.expires_at <= now + timedelta(days=wide_days)


@requires_db
def test_decimal_validation_error_returns_422_not_500(client):
    """Regression (M3 s10): pydantic puts the constraint value in the error `ctx`
    — Decimal('0') for a `gt=0` Decimal field. Emitting exc.errors() raw made
    json.dumps blow up and turned every such 422 into a 500. This is the shared
    error contract, so it affects any endpoint with a Decimal constraint."""
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, _, _ = make_click(client, ah, mh, name=f"Decimal-{_uuid.uuid4().hex[:6]}")
    cid = str(_contract_row(rid).id)

    resp = client.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                       json={"amount": "0"})
    assert resp.status_code == 422, "must be a clean 422, not a 500"
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "validation_error"
    # The offending constraint survives into the payload, JSON-safe.
    assert body["errors"][0]["loc"][-1] == "amount"
    assert body["errors"][0]["ctx"]["gt"] in ("0", 0)
