"""Commission CSV reconciliation + tier-based split (M2 slice 6)."""

from __future__ import annotations

import io
import uuid as _uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.services.earnings import split_commission_tiered
from tests.conftest import register_and_token, requires_db

SHOPEE_URL = "https://shopee.ph/product/abc-i.123.456"
HEADER = "click_ref,order_ref,gross_amount,currency,order_status,platform"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(("gross", "bps", "reviewer", "honesty"), [
    (Decimal("100.00"), 3000, Decimal("30.00"), Decimal("30.00")),
    (Decimal("100.00"), 3500, Decimal("35.00"), Decimal("30.00")),
    (Decimal("100.00"), 4000, Decimal("40.00"), Decimal("30.00")),
    (Decimal("0.01"), 3000, Decimal("0.00"), Decimal("0.00")),
    (Decimal("99.99"), 3500, Decimal("35.00"), Decimal("30.00")),
])
def test_split_commission_tiered_sums_exactly(gross, bps, reviewer, honesty):
    split = split_commission_tiered(gross, bps)
    assert split["reviewer_share"] == reviewer
    assert split["honesty_fund_share"] == honesty
    assert (split["platform_share"] + split["reviewer_share"]
            + split["honesty_fund_share"]) == split["gross_amount"] == gross


def test_split_commission_tiered_rejects_bps_over_7000():
    with pytest.raises(ValueError):
        split_commission_tiered(Decimal("100.00"), 7001)


def ensure_tier_configs() -> None:
    from app.db.session import SessionLocal
    from app.models.enums import MembershipTier
    from app.models.membership import MembershipTierConfig

    rows = [(MembershipTier.special, "Special", 4000, 1),
            (MembershipTier.founding, "Founding", 3500, 2),
            (MembershipTier.standard, "Standard", 3000, 3)]
    db = SessionLocal()
    try:
        for code, name, bps, priority in rows:
            cfg = db.query(MembershipTierConfig).filter_by(code=code).first()
            if cfg is None:
                db.add(MembershipTierConfig(code=code, name=name,
                                            revenue_share_bps=bps,
                                            payout_priority=priority))
            else:
                cfg.revenue_share_bps = bps
        db.commit()
    finally:
        db.close()


def make_click(client, author_headers, mod_headers, *, name: str) -> tuple[str, str, str]:
    """Monetized review + one click. Returns (review_id, click_ref, author_id)."""
    author_id = client.get("/api/v1/auth/me", headers=author_headers).json()["id"]
    pid = client.post("/api/v1/products", headers=author_headers,
                      json={"name": name, "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Great", "discussion": f"{name} held up well.",
            "verdict": "yes_absolutely", "star_rating": 4,
            "photo_url": "https://example.com/proof.jpg"}
    rid = client.post("/api/v1/reviews", headers=author_headers, json=body).json()["id"]
    attach = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mod_headers,
                         json={"url": SHOPEE_URL, "platform": "shopee"})
    assert attach.status_code == 200, attach.text
    assert client.get(f"/r/{rid}", follow_redirects=False).status_code == 302

    from app.db.session import SessionLocal
    from app.models.session import Session as ClickSession
    db = SessionLocal()
    try:
        click_ref = db.scalar(select(ClickSession.click_ref).where(
            ClickSession.review_id == _uuid.UUID(rid)))
    finally:
        db.close()
    return rid, click_ref, author_id


def _import(client, mod_headers, csv_text: str, filename: str = "commissions.csv"):
    return client.post("/api/v1/admin/commissions/import", headers=mod_headers,
                       files={"file": (filename, io.BytesIO(csv_text.encode()), "text/csv")})


def _wallet(author_id: str) -> Decimal:
    from app.db.session import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        return db.get(User, _uuid.UUID(author_id)).wallet_balance
    finally:
        db.close()


@requires_db
def test_full_import_flow_idempotent(client):
    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    rid, click_ref, author_id = make_click(
        client, ah, mh, name=f"CsvWidget-{_uuid.uuid4().hex[:6]}")
    wallet_before = _wallet(author_id)

    csv_text = (f"{HEADER}\n"
                f"{click_ref},ORD-1,100.00,PHP,completed,shopee\n"
                f"unknown_ref,,50.00,PHP,completed,lazada\n")
    resp = _import(client, mh, csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 1
    assert body["unmatched"] == [3]
    assert body["skipped_duplicates"] == 0
    assert body["total_rows"] == 2

    # Wallet credited with the standard-tier 30% share; snapshot recorded.
    assert _wallet(author_id) == wallet_before + Decimal("30.00")
    from app.db.session import SessionLocal
    from app.models.commission import Commission
    from app.models.session import Session as ClickSession
    db = SessionLocal()
    try:
        com = db.scalar(select(Commission).where(Commission.review_id == _uuid.UUID(rid)))
        assert com.reviewer_share_bps == 3000
        assert com.reviewer_tier.value == "standard"
        assert com.reviewer_share == Decimal("30.00")
        assert com.honesty_fund_share == Decimal("30.00")
        session = db.scalar(select(ClickSession).where(
            ClickSession.click_ref == click_ref))
        assert session.conversion_status.value == "converted"
        assert session.order_ref == "ORD-1"
    finally:
        db.close()

    # Re-import the SAME file: everything skipped, wallet unchanged.
    resp = _import(client, mh, csv_text)
    assert resp.json()["imported"] == 0
    assert resp.json()["skipped_duplicates"] == 1
    assert _wallet(author_id) == wallet_before + Decimal("30.00")


@requires_db
def test_import_rejects_tier_bps_above_cap(client):
    """A tier configured above 7000 bps would make the platform share negative;
    the import must refuse the whole file (config sanity check, 422)."""
    from app.db.session import SessionLocal
    from app.models.enums import MembershipTier
    from app.models.membership import MembershipTierConfig

    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    _, click_ref, author_id = make_click(
        client, ah, mh, name=f"BpsWidget-{_uuid.uuid4().hex[:6]}")
    wallet_before = _wallet(author_id)

    db = SessionLocal()
    try:
        cfg = db.query(MembershipTierConfig).filter_by(
            code=MembershipTier.standard).first()
        cfg.revenue_share_bps = 7001
        db.commit()

        csv_text = f"{HEADER}\n{click_ref},,100.00,PHP,completed,shopee\n"
        resp = _import(client, mh, csv_text, filename="bps.csv")
        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "tier_bps_invalid"
        assert resp.json()["tiers"] == {"standard": 7001}
        # Nothing imported, no wallet movement.
        assert _wallet(author_id) == wallet_before
    finally:
        cfg = db.query(MembershipTierConfig).filter_by(
            code=MembershipTier.standard).first()
        cfg.revenue_share_bps = 3000
        db.commit()
        db.close()


@requires_db
def test_import_validation_all_or_nothing_and_rbac(client):
    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    _, click_ref, author_id = make_click(client, ah, mh,
                                         name=f"BadCsvWidget-{_uuid.uuid4().hex[:6]}")
    wallet_before = _wallet(author_id)

    # One good row + one bad row -> 422, NOTHING imported.
    csv_text = (f"{HEADER}\n"
                f"{click_ref},,100.00,PHP,completed,shopee\n"
                f"someref,,not_a_number,PHP,completed,shopee\n")
    resp = _import(client, mh, csv_text, filename="bad.csv")
    assert resp.status_code == 422
    issues = resp.json()["errors"]
    assert issues == [{"line": 3, "issue": "gross_amount_not_decimal"}]
    assert _wallet(author_id) == wallet_before

    # Wrong currency and platform are rejected too.
    for row, issue in [
        (f"{click_ref},,10.00,USD,done,shopee", "currency_must_be_php"),
        (f"{click_ref},,10.00,PHP,done,ebay", "platform_invalid"),
        (",,10.00,PHP,done,shopee", "click_ref_or_order_ref_required"),
    ]:
        resp = _import(client, mh, f"{HEADER}\n{row}\n", filename="bad2.csv")
        assert resp.status_code == 422
        assert resp.json()["errors"][0]["issue"] == issue

    # RBAC: non-moderator forbidden.
    resp = _import(client, ah, f"{HEADER}\n{click_ref},,10.00,PHP,done,shopee\n")
    assert resp.status_code == 403
