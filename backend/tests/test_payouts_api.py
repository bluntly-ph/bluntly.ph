"""Payouts — tier-priority scheduling, wallet reserve/refund, PayPal adapter
(mocked), manual rail (M3 slice 11).

No test makes a real PayPal call: the adapter is monkeypatched, per the plan.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.adapters import paypal
from app.core.config import settings
from app.models.enums import MembershipTier, PayoutStatus
from app.services import payout_service
from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _set_wallet(uid: str, amount: str, tier: MembershipTier | None = None,
                account: str | None = "payee@example.com") -> None:
    """Fund a wallet the way the platform really does — via a commission whose
    reviewer_share IS the target amount.

    Setting `wallet_balance` directly would fabricate money with no row behind
    it and break the whole-database invariant
    `wallet == inflows - reserved payouts` (scripts/supabase_verify.py), which is
    exactly the drift that invariant exists to catch.
    """
    from datetime import date

    from app.db.session import SessionLocal
    from app.models.honesty_fund import HonestyFundDistribution
    from app.models.user import User

    # Honesty Fund payout is the simplest legitimate inflow to synthesise: unlike
    # `commissions` (ck_commission_target demands a review_id) it allows a null
    # review, so no product/review scaffolding is needed just to fund a wallet.
    target = Decimal(amount)
    db = SessionLocal()
    try:
        u = db.get(User, _uuid.UUID(uid))
        u.payout_account = account
        if tier is not None:
            u.membership_tier = tier
        # Clear prior fixture funding so `target` is the whole balance.
        for old in db.scalars(select(HonestyFundDistribution).where(
                HonestyFundDistribution.reviewer_id == u.id,
                HonestyFundDistribution.distribution_id.like("hfd_payfix_%"))):
            db.delete(old)
        db.flush()
        if target > 0:
            db.add(HonestyFundDistribution(
                distribution_id=f"hfd_payfix_{_uuid.uuid4().hex[:8]}",
                cycle_month=date(1970, 1, 1), review_id=None, reviewer_id=u.id,
                honesty_score=Decimal("1"), pool_amount=target,
                payout_amount=target))
        u.wallet_balance = target
        db.commit()
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


def _payouts_for(uid: str) -> list:
    from app.db.session import SessionLocal
    from app.models.payout import Payout

    db = SessionLocal()
    try:
        return list(db.scalars(select(Payout).where(Payout.user_id == _uuid.UUID(uid))))
    finally:
        db.close()


def _free_when() -> date:
    """A scheduling date whose batch_id is unused.

    `schedule_payouts` is deliberately GLOBAL (it sweeps every eligible user) and
    the batch key is `batch_YYYYMM`, so consecutive suite runs would otherwise
    share a batch and trip uq_payout_user_batch. A unique historic month gives
    each test its own batch without weakening the real monthly behaviour.
    """
    from app.db.session import SessionLocal
    from app.models.payout import Payout

    db = SessionLocal()
    try:
        used = {b for b in db.scalars(select(Payout.batch_id).distinct()) if b}
        for year in range(1990, 2100):
            for month in range(1, 13):
                when = date(year, month, 5)
                if payout_service.batch_id_for(when) not in used:
                    return when
        raise AssertionError("no free payout batch month")
    finally:
        db.close()


@requires_db
def test_payout_account_setter_validates_email(client):
    _, token, _ = register_and_token(client)
    h = _auth(token)
    assert client.patch("/api/v1/auth/me/payout-account", headers=h,
                        json={"payout_account": "not-an-email"}).status_code == 422
    r = client.patch("/api/v1/auth/me/payout-account", headers=h,
                     json={"payout_account": "me@example.com"})
    assert r.status_code == 200 and r.json()["payout_account"] == "me@example.com"
    assert client.patch("/api/v1/auth/me/payout-account",
                        json={"payout_account": "me@example.com"}).status_code == 401


@requires_db
def test_scheduler_eligibility_reserve_and_tier_order(client, monkeypatch):
    from app.db.session import SessionLocal
    from tests.test_commissions_api import ensure_tier_configs

    ensure_tier_configs()
    monkeypatch.setattr(settings, "payout_provider", "manual")
    when = _free_when()

    rich_std, t1, _ = register_and_token(client)
    founding, t2, _ = register_and_token(client)
    special, t3, _ = register_and_token(client)
    poor, t4, _ = register_and_token(client)
    no_acct, t5, _ = register_and_token(client)

    _set_wallet(rich_std, "500.00", MembershipTier.standard)
    _set_wallet(founding, "400.00", MembershipTier.founding)
    _set_wallet(special, "350.00", MembershipTier.special)
    _set_wallet(poor, "299.99", MembershipTier.standard)          # below the minimum
    _set_wallet(no_acct, "900.00", MembershipTier.standard, account=None)

    db = SessionLocal()
    try:
        result = payout_service.schedule_payouts(db, when=when)
    finally:
        db.close()

    assert result["scheduled"] >= 3
    assert result["skipped_no_payout_account"] >= 1
    assert result["method"] == "manual"

    # Eligible users got a payout for their full balance; wallet reserved to 0.
    for uid, amount in ((rich_std, "500.00"), (founding, "400.00"), (special, "350.00")):
        ps = _payouts_for(uid)
        assert len(ps) == 1 and ps[0].amount == Decimal(amount)
        assert ps[0].status == PayoutStatus.scheduled
        assert _wallet(uid) == Decimal("0.00")

    # Below-minimum and no-account users are untouched.
    assert _payouts_for(poor) == [] and _wallet(poor) == Decimal("299.99")
    assert _payouts_for(no_acct) == [] and _wallet(no_acct) == Decimal("900.00")

    # Tier priority drives the order: special(1) -> founding(2) -> standard(3).
    db = SessionLocal()
    try:
        batch = result["batch_id"]
        rows = list(db.scalars(select(payout_service.Payout).where(
            payout_service.Payout.batch_id == batch).order_by(
            payout_service.Payout.created_at)))
    finally:
        db.close()
    mine = {special, founding, rich_std}
    order = [str(p.user_id) for p in rows if str(p.user_id) in mine]
    assert order == [special, founding, rich_std], (
        'tier payout_priority must drive the order: special -> founding -> standard')


@requires_db
def test_scheduler_is_idempotent_within_a_batch(client, monkeypatch):
    from app.db.session import SessionLocal
    from tests.test_commissions_api import ensure_tier_configs

    ensure_tier_configs()
    monkeypatch.setattr(settings, "payout_provider", "manual")
    when = _free_when()
    uid, token, _ = register_and_token(client)
    _set_wallet(uid, "600.00")

    db = SessionLocal()
    try:
        payout_service.schedule_payouts(db, when=when)
        assert _wallet(uid) == Decimal("0.00")
        # Re-running the same month must not double-schedule or re-debit.
        payout_service.schedule_payouts(db, when=when)
    finally:
        db.close()
    assert len(_payouts_for(uid)) == 1
    assert _wallet(uid) == Decimal("0.00")


@requires_db
def test_manual_mark_paid_and_rbac(client, monkeypatch):
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "payout_provider", "manual")
    when = _free_when()
    uid, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    h, mh = _auth(token), _auth(mod_token)
    _set_wallet(uid, "450.00")
    db = SessionLocal()
    try:
        payout_service.schedule_payouts(db, when=when)
    finally:
        db.close()
    pid = str(_payouts_for(uid)[0].id)

    # Own payouts are visible; another user can't see them.
    assert pid in [p["id"] for p in client.get("/api/v1/payouts", headers=h).json()]
    _, other, _ = register_and_token(client)
    assert client.get("/api/v1/payouts", headers=_auth(other)).json() == []
    # RBAC on the admin surface.
    assert client.get("/api/v1/admin/payouts", headers=h).status_code == 403
    assert client.post(f"/api/v1/admin/payouts/{pid}/mark-paid", headers=h,
                       json={"provider_ref": "X"}).status_code == 403

    r = client.post(f"/api/v1/admin/payouts/{pid}/mark-paid", headers=mh,
                    json={"provider_ref": "MANUAL-REF-1"})
    assert r.status_code == 200
    assert r.json()["status"] == "paid" and r.json()["provider_ref"] == "MANUAL-REF-1"
    assert r.json()["paid_at"] is not None
    assert _wallet(uid) == Decimal("0.00")   # stays debited — it was paid
    # Can't pay twice.
    assert client.post(f"/api/v1/admin/payouts/{pid}/mark-paid", headers=mh,
                       json={"provider_ref": "AGAIN"}).status_code == 409


@requires_db
def test_failure_and_cancel_refund_the_wallet(client, monkeypatch):
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "payout_provider", "manual")
    when = _free_when()
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    # Failure path.
    uid, _, _ = register_and_token(client)
    _set_wallet(uid, "500.00")
    db = SessionLocal()
    try:
        payout_service.schedule_payouts(db, when=when)
    finally:
        db.close()
    pid = str(_payouts_for(uid)[0].id)
    assert _wallet(uid) == Decimal("0.00")
    r = client.post(f"/api/v1/admin/payouts/{pid}/fail", headers=mh,
                    json={"reason": "bad receiver account"})
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert _wallet(uid) == Decimal("500.00")     # refunded — earnings not lost

    # Retry re-reserves it.
    r = client.post(f"/api/v1/admin/payouts/{pid}/retry", headers=mh)
    assert r.status_code == 200 and r.json()["status"] == "scheduled"
    assert _wallet(uid) == Decimal("0.00")

    # Cancel path refunds too.
    r = client.post(f"/api/v1/admin/payouts/{pid}/cancel", headers=mh)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert _wallet(uid) == Decimal("500.00")
    # A cancelled payout can't be cancelled again.
    assert client.post(f"/api/v1/admin/payouts/{pid}/cancel", headers=mh).status_code == 409


@requires_db
def test_paypal_adapter_receives_correct_payload(client, monkeypatch):
    """The adapter is mocked — assert we call it with exactly the documented shape."""
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "payout_provider", "paypal_sandbox")
    when = _free_when()
    monkeypatch.setattr(paypal, "is_configured", lambda: True)
    captured: dict = {}

    def fake_submit(sender_batch_id, items):
        captured["batch"] = sender_batch_id
        captured["items"] = items
        return paypal.BatchResult(payout_batch_id="PB-123", batch_status=paypal.BATCH_PENDING)

    monkeypatch.setattr(paypal, "submit_batch", fake_submit)

    uid, _, _ = register_and_token(client)
    _set_wallet(uid, "750.00", account="payee-x@example.com")
    db = SessionLocal()
    try:
        result = payout_service.schedule_payouts(db, when=when)
        sub = payout_service.submit_batch(db, result["batch_id"])
    finally:
        db.close()

    assert sub["status"] == "processing" and sub["provider_ref"] == "PB-123"
    assert captured["batch"] == result["batch_id"]
    mine = [i for i in captured["items"] if i.receiver == "payee-x@example.com"]
    assert len(mine) == 1
    assert mine[0].amount == Decimal("750.00")
    assert mine[0].currency == "PHP"
    assert mine[0].sender_item_id == _payouts_for(uid)[0].payout_id
    assert _payouts_for(uid)[0].status == PayoutStatus.processing


@requires_db
def test_missing_credentials_leaves_batch_scheduled_not_crashing(client, monkeypatch):
    """No PayPal creds must NOT be an error — the manual rail stays available."""
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "payout_provider", "paypal_sandbox")
    when = _free_when()
    monkeypatch.setattr(paypal, "is_configured", lambda: False)
    uid, _, _ = register_and_token(client)
    _set_wallet(uid, "800.00")
    db = SessionLocal()
    try:
        result = payout_service.schedule_payouts(db, when=when)
        sub = payout_service.submit_batch(db, result["batch_id"])
    finally:
        db.close()
    assert sub["status"] == "provider_not_configured"
    assert _payouts_for(uid)[0].status == PayoutStatus.scheduled  # still payable by hand
    assert _wallet(uid) == Decimal("0.00")


@requires_db
def test_refresh_settles_success_and_failure(client, monkeypatch):
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "payout_provider", "paypal_sandbox")
    when = _free_when()
    monkeypatch.setattr(paypal, "is_configured", lambda: True)
    monkeypatch.setattr(paypal, "submit_batch", lambda b, i: paypal.BatchResult(
        payout_batch_id="PB-REFRESH", batch_status=paypal.BATCH_PENDING))

    winner, _, _ = register_and_token(client)
    loser, _, _ = register_and_token(client)
    _set_wallet(winner, "500.00", account="win@example.com")
    _set_wallet(loser, "600.00", account="lose@example.com")
    db = SessionLocal()
    try:
        result = payout_service.schedule_payouts(db, when=when)
        payout_service.submit_batch(db, result["batch_id"])
    finally:
        db.close()

    win_pid = _payouts_for(winner)[0].payout_id
    lose_pid = _payouts_for(loser)[0].payout_id
    monkeypatch.setattr(paypal, "get_batch", lambda ref: {
        "batch_status": paypal.BATCH_PROCESSING,
        "items": {win_pid: paypal.TXN_SUCCESS, lose_pid: paypal.TXN_FAILED}})

    db = SessionLocal()
    try:
        out = payout_service.refresh_batch(db, result["batch_id"])
    finally:
        db.close()
    assert out["paid"] >= 1 and out["failed"] >= 1
    assert _payouts_for(winner)[0].status == PayoutStatus.paid
    assert _wallet(winner) == Decimal("0.00")          # paid: stays debited
    assert _payouts_for(loser)[0].status == PayoutStatus.failed
    assert _wallet(loser) == Decimal("600.00")         # failed: refunded


@pytest.mark.parametrize("txn", sorted(paypal.TXN_FAILURES))
def test_every_documented_failure_status_is_treated_as_failure(txn):
    """PayPal's transaction_status enum has several terminal-failure values; each
    must refund rather than silently strand the money."""
    assert txn in paypal.TXN_FAILURES
    assert txn not in (paypal.TXN_SUCCESS, paypal.TXN_PENDING,
                       paypal.TXN_UNCLAIMED, paypal.TXN_ONHOLD)


def test_live_provider_requires_credentials_and_non_sandbox_url():
    from app.core.config import Settings

    # Every field this assertion depends on is passed explicitly: Settings also
    # reads the repo-root .env, so a developer with real PAYPAL_* values
    # configured would otherwise see the credentials check correctly pass and
    # this test fail for reasons that have nothing to do with the code.
    s = Settings(app_env="production", payout_provider="paypal_live",
                 paypal_client_id="", paypal_secret="",
                 paypal_base_url="https://api-m.sandbox.paypal.com",
                 jwt_secret="x" * 40, pii_hash_salt="y" * 40,
                 use_supabase=True, supabase_connection_string="postgresql://x/y")
    issues = " ".join(s.production_issues())
    assert "PAYPAL_CLIENT_ID" in issues
    assert "sandbox" in issues
