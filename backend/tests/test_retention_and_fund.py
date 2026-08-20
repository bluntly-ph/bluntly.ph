"""PII retention sweep + Honesty Fund distribution (M2 slice 8)."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.commission import Commission
from app.models.honesty_fund import HonestyFundDistribution
from tests.conftest import owned_photo_url, register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_session(db, *, days_ago: int, ip: str = "203.0.113.7",
                  ua: str = "TestAgent/1.0"):
    from app.models.session import Session as ClickSession
    from app.services.pii import retention_deadlines

    clicked = datetime.now(UTC) - timedelta(days=days_ago)
    deadlines = retention_deadlines(clicked)
    row = ClickSession(
        session_id=f"clk_test_{_uuid.uuid4().hex[:12]}",
        click_ref=f"ref_test_{_uuid.uuid4().hex[:12]}",
        clicked_at=clicked, ip_address=ip, user_agent=ua,
        ua_purge_at=deadlines["ua_purge_at"], ip_hash_at=deadlines["ip_hash_at"],
        ip_delete_at=deadlines["ip_delete_at"],
    )
    db.add(row)
    db.flush()
    return row.id


@requires_db
def test_retention_sweep_30_and_90_day_boundaries(client):
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.session import Session as ClickSession
    from app.services.pii import hash_ip
    from app.services.retention_service import run_retention_sweep

    db = SessionLocal()
    try:
        fresh = _make_session(db, days_ago=5)
        due_hash = _make_session(db, days_ago=31, ip="198.51.100.4")
        due_purge = _make_session(db, days_ago=91)
        db.commit()

        counts = run_retention_sweep(db)
        assert counts["hashed"] >= 1  # global sweep may touch older fixtures too
        assert counts["purged"] >= 1

        fresh_row = db.get(ClickSession, fresh)
        assert fresh_row.ip_address is not None and fresh_row.user_agent is not None

        hashed_row = db.get(ClickSession, due_hash)
        assert hashed_row.ip_address is None
        # SQL sha256 must be byte-for-byte identical to services.pii.hash_ip.
        assert hashed_row.ip_hash == hash_ip("198.51.100.4", settings.pii_hash_salt)
        assert hashed_row.user_agent is not None  # UA only purges at 90d

        purged_row = db.get(ClickSession, due_purge)
        assert purged_row.ip_address is None
        assert purged_row.ip_hash is None
        assert purged_row.user_agent is None

        # Second run is a no-op for these rows (deterministic sweep).
        run_retention_sweep(db)
        assert db.get(ClickSession, due_hash).ip_hash == hash_ip(
            "198.51.100.4", settings.pii_hash_salt)
    finally:
        db.close()


def _honesty_review(client, mod_headers, *, price: str, name: str) -> tuple[str, str]:
    """A published 2-star review (routes to the Honesty Fund). Returns (rid, author_id)."""
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]
    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": name, "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Disappointing", "price_paid": price,
            "discussion": f"{name}: broke fast; honest warning.",
            "verdict": "hard_pass", "star_rating": 2,
            "photo_url": owned_photo_url(ah)}
    rid = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]
    resp = client.post(f"/api/v1/admin/reviews/{rid}/publish", headers=mod_headers)
    assert resp.status_code == 200
    assert resp.json()["earn_eligible_status"] == "honesty_fund"
    return rid, author_id


def _weighted_upvote(client, rid: str, *, stage: int, reputation: float) -> None:
    """Up-vote from a voter whose trust snapshot is set directly (deterministic)."""
    import uuid

    from app.db.session import SessionLocal
    from app.models.user import User

    uid, token, _ = register_and_token(client)
    db = SessionLocal()
    try:
        voter = db.get(User, uuid.UUID(uid))
        voter.trust_stage = stage
        voter.reputation_score = reputation
        voter.created_at = datetime.now(UTC) - timedelta(days=60)  # matured
        db.commit()
    finally:
        db.close()
    resp = client.post(f"/api/v1/reviews/{rid}/vote", headers=_auth(token),
                       json={"vote": "up"})
    assert resp.status_code == 200, resp.text


def _seed_pool(cycle: date, amount: Decimal, review_id: str) -> None:
    """Insert a commission carrying `amount` of honesty-fund share for `cycle`.

    Uses the real split so the row is arithmetically valid (the three shares must
    always re-sum to gross — a whole-database invariant asserted by
    scripts/supabase_verify.py). Honesty Fund is a fixed 30%, so a pool of
    `amount` comes from a gross of amount/0.30. `reviewer_id` is intentionally
    left NULL: no wallet is credited by this raw insert, and a reviewer_id here
    would break the wallet == SUM(sources) invariant.
    """
    from app.db.session import SessionLocal
    from app.models.commission import Commission
    from app.models.enums import CommissionTarget
    from app.services.earnings import split_commission

    gross = (amount / Decimal("0.30")).quantize(Decimal("0.01"))
    split = split_commission(gross)
    assert split["honesty_fund_share"] == amount, "fixture pool must equal the 30% share"
    db = SessionLocal()
    try:
        db.add(Commission(
            commission_id=f"com_test_{_uuid.uuid4().hex[:10]}",
            target_type=CommissionTarget.review, review_id=_uuid.UUID(review_id),
            csv_source=f"test:{_uuid.uuid4().hex[:12]}", row_reference="2",
            cycle_month=cycle, **split,
        ))
        db.commit()
    finally:
        db.close()


def _free_cycle() -> date:
    """A historic cycle_month with no distributions or commissions yet.

    The Honesty Fund is idempotent per cycle: a second run for the same cycle
    correctly ABORTS. A blind random draw therefore collides with an earlier
    test run's cycle on a long-lived DB (~4% per suite run, rising with every
    run) and fails a test the app got right. Ask the DB for a free slot instead.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        used = {r[0] for r in db.execute(select(HonestyFundDistribution.cycle_month)
                                         .distinct())}
        used |= {r[0] for r in db.execute(select(Commission.cycle_month).distinct())}
        for year in range(1900, 2100):
            for month in range(1, 13):
                cycle = date(year, month, 1)
                if cycle not in used:
                    return cycle
        raise AssertionError("no free cycle_month available")
    finally:
        db.close()


@requires_db
def test_honesty_fund_distribution_proportional_and_idempotent(client):
    from app.db.session import SessionLocal
    from app.models.honesty_fund import HonestyFundDistribution
    from app.services.honesty_fund_service import distribute

    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    tag = _uuid.uuid4().hex[:6]

    # Stage-2 voter at rep 100 -> weight 1.0; at rep 50 -> 0.5. Same price bracket.
    r1, a1 = _honesty_review(client, mh, price="100", name=f"Fund1-{tag}")
    r2, a2 = _honesty_review(client, mh, price="100", name=f"Fund2-{tag}")
    r3, _ = _honesty_review(client, mh, price="100", name=f"Fund3-{tag}")
    _weighted_upvote(client, r1, stage=2, reputation=100.0)
    _weighted_upvote(client, r2, stage=2, reputation=50.0)
    # r3 gets no votes -> score 0 -> no share.

    cycle = _free_cycle()
    _seed_pool(cycle, Decimal("30.00"), r1)

    db = SessionLocal()
    try:
        result = distribute(db, cycle_month=cycle)
        assert result["status"] == "distributed"
        assert result["pool"] == "30.00"

        rows = {str(d.review_id): d for d in db.scalars(
            select(HonestyFundDistribution).where(
                HonestyFundDistribution.cycle_month == cycle))}
        assert r1 in rows and r2 in rows and r3 not in rows
        p1, p2 = rows[r1].payout_amount, rows[r2].payout_amount
        # Scores are 1.0 vs 0.5 -> payouts split 2:1 (floor rounding, dust stays).
        assert p1 > p2 > 0
        assert abs(p1 - 2 * p2) <= Decimal("0.02")
        assert p1 + p2 <= Decimal("30.00")

        # Second run for the same cycle ABORTS.
        again = distribute(db, cycle_month=cycle)
        assert again["status"] == "already_distributed"

        # Empty pool cycle -> no-op.
        empty = distribute(db, cycle_month=date(1949, 1, 1))
        assert empty["status"] == "empty_pool"
    finally:
        db.close()


@requires_db
def test_honesty_fund_admin_endpoint(client):
    _, user_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    tag = _uuid.uuid4().hex[:6]

    rid, _ = _honesty_review(client, mh, price="600", name=f"FundAdmin-{tag}")
    _weighted_upvote(client, rid, stage=2, reputation=100.0)
    cycle = _free_cycle()
    _seed_pool(cycle, Decimal("15.00"), rid)

    # RBAC: plain user forbidden.
    assert client.post("/api/v1/admin/honesty-fund/run", headers=_auth(user_token),
                       json={}).status_code == 403

    resp = client.post("/api/v1/admin/honesty-fund/run", headers=mh,
                       json={"cycle_month": f"{cycle.year:04d}-{cycle.month:02d}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "distributed"
    assert body["recipients"] >= 1
