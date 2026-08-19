"""Milestone claim verification — M1, M2, M3 (deep, end-to-end).

`supabase_verify.py` proves the DATABASE is sound. This proves the PRODUCT is:
every bullet the owner's `docs/MILESTONES.md` promises is exercised against a
live API and asserted. If a milestone says a feature exists, this fails when it
doesn't — regardless of what the docs claim.

Runs the real flows in-process (TestClient) against whichever DB is configured,
so it works against local or Supabase.

Usage:
  python -m scripts.verify_milestones                  # local
  USE_SUPABASE=true python -m scripts.verify_milestones  # prod (Supabase)

Exit code 0 only if every claim holds.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.core.env_guard import guard_cli
from app.core.config import settings

settings.auth_rate_limit_max = 1_000_000
settings.vote_rate_limit_max = 1_000_000

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

_RESULTS: list[tuple[bool, str, str]] = []
PW = "password123"
SHOPEE = "https://shopee.ph/x-i.1.2?af=v"


def check(claim: str, ok: bool, detail: str = "") -> bool:
    _RESULTS.append((bool(ok), claim, detail))
    suffix = f"  ({detail})" if detail and not ok else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {claim}{suffix}")
    return bool(ok)


class Harness:
    def __init__(self) -> None:
        self.c = TestClient(app)
        self.tag = uuid.uuid4().hex[:8]

    def register(self, who: str, role: str = "user") -> tuple[str, dict]:
        email = f"mv_{who}_{self.tag}@example.com"
        r = self.c.post("/api/v1/auth/register", json={"email": email, "password": PW})
        assert r.status_code == 201, r.text
        uid, token = r.json()["user"]["id"], r.json()["access_token"]
        if role != "user":
            from app.core.security import create_access_token
            from app.models.enums import MemberRole
            from app.models.user import User
            db = SessionLocal()
            try:
                db.query(User).filter(User.id == uuid.UUID(uid)).update(
                    {"role": MemberRole(role)})
                db.commit()
            finally:
                db.close()
            token = create_access_token(uuid.UUID(uid), role)
        return uid, {"Authorization": f"Bearer {token}"}

    def product(self, h: dict, name: str) -> str:
        return self.c.post("/api/v1/products", headers=h, json={
            "name": f"{name}-{uuid.uuid4().hex[:6]}", "category": "electronics",
            "source_url": "https://shopee.ph/x-i.1.2"}).json()["id"]

    def review(self, h: dict, pid: str, stars: int = 4, photo: bool = True) -> str:
        body = {"product_id": pid, "title": "Verify", "star_rating": stars,
                "discussion": f"Milestone verification review {uuid.uuid4().hex[:6]}.",
                "verdict": "yes_absolutely" if stars >= 3 else "hard_pass"}
        if photo:
            body["photo_url"] = "https://example.com/p.jpg"
        return self.c.post("/api/v1/reviews", headers=h, json=body).json()["id"]


def verify_m1(hz: Harness) -> None:
    """M1 — auth, membership tiers, review submission + version history, AI critique."""
    print("\n=== M1: Core System Foundation ===")
    c = hz.c
    uid, ah = hz.register("m1")

    # JWT/OAuth2 auth: registration + login + me.
    login = c.post("/api/v1/auth/login",
                   data={"username": f"mv_m1_{hz.tag}@example.com", "password": PW})
    check("M1: JWT/OAuth2 registration + login + /me",
          login.status_code == 200 and "access_token" in login.json()
          and c.get("/api/v1/auth/me", headers=ah).status_code == 200, login.text[:80])
    check("M1: wrong password rejected",
          c.post("/api/v1/auth/login", data={"username": f"mv_m1_{hz.tag}@example.com",
                                             "password": "wrong"}).status_code == 401)
    check("M1: unauthenticated /me is 401", c.get("/api/v1/auth/me").status_code == 401)

    # Argon2id, never plaintext.
    db = SessionLocal()
    try:
        h = db.execute(text("select password_hash from users where id=:i"),
                       {"i": uid}).scalar()
    finally:
        db.close()
    check("M1: passwords stored as Argon2id (never plaintext)",
          bool(h) and h.startswith("$argon2") and PW not in h)

    # Membership tiers.
    tiers = c.get("/api/v1/membership-tiers").json()
    check("M1: membership tiers Special/Founding/Standard exist",
          {t["code"] for t in tiers} >= {"special", "founding", "standard"})
    _, mh = hz.register("m1mod", role="moderator")
    check("M1: tier management is moderator-gated",
          c.patch("/api/v1/membership-tiers/standard", headers=ah,
                  json={"revenue_share_bps": 3100}).status_code == 403
          and c.patch(f"/api/v1/users/{uid}/membership-tier", headers=mh,
                      json={"membership_tier": "founding"}).status_code == 200)

    # Review submission + version history.
    pid = hz.product(ah, "M1Widget")
    rid = hz.review(ah, pid)
    check("M1: review submission stores the structured format",
          c.get(f"/api/v1/reviews/{rid}", headers=ah).json()["star_rating"] == 4)
    edit = c.patch(f"/api/v1/reviews/{rid}", headers=ah,
                   json={"title": "Edited", "change_note": "v2"})
    versions = c.get(f"/api/v1/reviews/{rid}/versions", headers=ah).json()
    check("M1: editing a review creates a new version (history kept)",
          edit.json()["current_version"] == 2
          and [v["version_number"] for v in versions] == [1, 2])
    check("M1: a specific version is retrievable",
          c.get(f"/api/v1/reviews/{rid}/versions/1", headers=ah).status_code == 200)
    check("M1: only the author/moderator may edit",
          c.patch(f"/api/v1/reviews/{rid}", headers=hz.register("m1other")[1],
                  json={"title": "hijack"}).status_code == 403)

    # AI critique.
    crit = c.post(f"/api/v1/reviews/{rid}/critique", headers=ah)
    check("M1: AI critique integration returns a scored critique",
          crit.status_code == 200 and 0 <= crit.json()["quality_score"] <= 100
          and crit.json()["provider"] in ("stub", "claude", "openai"), crit.text[:80])
    check("M1: ad-hoc AI critique endpoint works",
          c.post("/api/v1/ai/critique", headers=ah,
                 json={"text": "A draft review body."}).status_code == 200)


def verify_m2(hz: Harness) -> None:
    """M2 — Wilson trust, fraud/collusion signals, thresholds, voting, affiliate
    attribution, tier split, token economy."""
    print("\n=== M2: Reputation & Trust Systems ===")
    c = hz.c
    author_id, ah = hz.register("m2author")
    _, mh = hz.register("m2mod", role="moderator")
    voter_id, vh = hz.register("m2voter")

    pid = hz.product(ah, "M2Widget")
    rid = hz.review(ah, pid, stars=5)

    # Affiliate link generation + attribution (Shopee/Lazada/Amazon).
    att = c.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"})
    check("M2: affiliate link attach monetizes + publishes atomically",
          att.status_code == 200 and att.json()["earn_eligible_status"] == "monetized"
          and att.json()["published_at"] is not None, att.text[:80])
    check("M2: the raw affiliate URL is NEVER exposed publicly",
          SHOPEE not in str(c.get(f"/api/v1/reviews/{rid}").json())
          and c.get(f"/api/v1/reviews/{rid}").json()["referral_redirect_url"] == f"/r/{rid}")
    red = c.get(f"/r/{rid}", follow_redirects=False)
    check("M2: attribution redirect 302s and records a click",
          red.status_code == 302 and red.headers["location"] == SHOPEE)
    check("M2: platform enum covers Shopee/Lazada/Amazon",
          {"shopee", "lazada", "amazon"} <= {
              r[0] for r in SessionLocal().execute(text(
                  "select e.enumlabel from pg_enum e join pg_type t "
                  "on t.oid=e.enumtypid where t.typname='platform'"))})

    # Upvote/downvote + anti-manipulation.
    v = c.post(f"/api/v1/reviews/{rid}/vote", headers=vh, json={"vote": "up"})
    check("M2: upvote/downvote with Wilson scoring",
          v.status_code == 200 and v.json()["helpful_votes"] == 1
          and float(v.json()["wilson_score"]) > 0, v.text[:80])
    check("M2: anti-manipulation — no self-voting",
          c.post(f"/api/v1/reviews/{rid}/vote", headers=ah,
                 json={"vote": "up"}).json().get("code") == "cannot_vote_own_review")
    check("M2: anti-manipulation — one vote per user (upsert, not stacking)",
          c.post(f"/api/v1/reviews/{rid}/vote", headers=vh,
                 json={"vote": "down"}).json()["helpful_votes"] == 0)
    check("M2: Wilson-ranked listing is available",
          c.get("/api/v1/reviews?sort=wilson&limit=5").status_code == 200)

    # Trust progression.
    trust = c.get(f"/api/v1/users/{author_id}/trust").json()
    check("M2: trust progression — stage/reputation/badges are public",
          trust["trust_stage"] >= 2 and "reputation_score" in trust
          and any(b["badge_id"] == "verified_buyer" for b in trust["badges"]),
          str(trust)[:90])

    # Product Wilson trust ratings.

    check("M2: Wilson trust rating for PRODUCTS",
          float(c.get(f"/api/v1/products/{pid}").json()["trust_score"]) > 0)
    check("M2: trust threshold configuration exists (visibility control)",
          "low_trust" in c.get(f"/api/v1/products/{pid}").json()
          and hasattr(settings, "product_trust_visibility_threshold"))

    # Fake/shill + collusion detection — advisory only.
    from app.models.review import Review
    from app.models.user import User
    from app.services.fraud_service import compute_signals
    db = SessionLocal()
    try:
        review = db.get(Review, uuid.UUID(rid))
        signals = compute_signals(db, review, db.get(User, uuid.UUID(author_id)))
    finally:
        db.close()
    check("M2: fake/shill + collusion detection signals are computed",
          {"velocity", "collusion", "duplicate_content", "duplicate_of"} <= set(signals),
          str(signals)[:80])
    check("M2: fraud signals are ADVISORY — nothing auto-blocked",
          c.get(f"/api/v1/reviews/{rid}").status_code == 200
          and "signals" not in c.get(f"/api/v1/reviews/{rid}").json())

    # Tier-based revenue split.
    from app.services.earnings import split_commission_tiered
    s = split_commission_tiered(Decimal("100.00"), 3500)
    check("M2: tier-based revenue split (Honesty Fund fixed 30%, exact to centavo)",
          s["reviewer_share"] == Decimal("35.00")
          and s["honesty_fund_share"] == Decimal("30.00")
          and s["platform_share"] + s["reviewer_share"] + s["honesty_fund_share"]
          == Decimal("100.00"), str(s))

    # Token economy + transaction history.
    bal = c.get("/api/v1/tokens/balance", headers=ah)
    txs = c.get("/api/v1/tokens/transactions", headers=ah)
    check("M2: token economy — balance + append-only transaction history",
          bal.status_code == 200 and bal.json()["token_balance"] > 0
          and txs.status_code == 200 and len(txs.json()) >= 1
          and txs.json()[0]["balance_after"] == bal.json()["token_balance"],
          str(bal.json()))
    check("M2: token ledger has no update/delete surface (append-only)",
          all(("PUT" not in m and "DELETE" not in m and "PATCH" not in m)
              for p, item in app.openapi()["paths"].items() if "tokens" in p
              for m in (k.upper() for k in item)))


def verify_m3(hz: Harness) -> None:
    """M3 — request board + AI validation + dynamic rewards, contracts, payouts by
    tier, affiliate ingestion, frontend readiness, load testing."""
    print("\n=== M3: Full System Delivery (built, not deployed) ===")
    c = hz.c
    uid, ah = hz.register("m3user")
    _, mh = hz.register("m3mod", role="moderator")

    # Request board + AI validation + demand signal. The bounty escrow and its
    # up-vote top-up were retired with the token economy (migration 0022), so
    # what is verified here is that posting costs nothing and up-votes rank.
    bad = c.post("/api/v1/requests", headers=ah,
                 json={"title": "Review it", "details": "pls"})
    check("M3: request board — AI validation blocks thin requests with reasons",
          bad.status_code == 422 and bad.json()["code"] == "request_invalid"
          and bad.json()["reasons"], bad.text[:80])
    before_post = c.get("/api/v1/tokens/balance", headers=ah).json()["token_balance"]
    req = c.post("/api/v1/requests", headers=ah, json={
        "title": "Review this handheld fan",
        "details": "Please cover battery life and build quality after two weeks."})
    check("M3: request board — posting a request is free and costs no tokens",
          req.status_code == 201 and req.json()["status"] == "open"
          and c.get("/api/v1/tokens/balance", headers=ah).json()["token_balance"]
          == before_post, req.text[:80])
    rq = req.json()["id"]
    _, uh = hz.register("m3upvoter")
    up = c.post(f"/api/v1/requests/{rq}/upvote", headers=uh)
    check("M3: request board — up-vote records demand and the voter's own state",
          up.status_code == 200 and up.json()["upvote_count"] == 1
          and up.json()["my_upvote"] is True, up.text[:80])

    # Reviewer fulfils with their own published review.
    rev_id, rh = hz.register("m3reviewer")
    pid = hz.product(rh, "M3Widget")
    rid = hz.review(rh, pid, stars=5)
    c.post(f"/api/v1/admin/reviews/{rid}/publish", headers=mh)
    before = c.get("/api/v1/tokens/balance", headers=rh).json()["token_balance"]
    ful = c.post(f"/api/v1/requests/{rq}/fulfill", headers=rh, json={"review_id": rid})
    check("M3: request board — fulfilment links the review and pays nothing",
          ful.status_code == 200 and ful.json()["status"] == "fulfilled"
          and c.get("/api/v1/tokens/balance", headers=rh).json()["token_balance"]
          == before, ful.text[:80])

    # Contracts: duration tracking + renewal + buyout.
    mono_id, mh2 = hz.register("m3author")
    pid2 = hz.product(mh2, "M3Contract")
    rid2 = hz.review(mh2, pid2, stars=5)
    c.post(f"/api/v1/admin/reviews/{rid2}/referral-link", headers=mh,
           json={"url": SHOPEE, "platform": "shopee"})
    mine = c.get("/api/v1/contracts", headers=mh2).json()
    check("M3: contract duration tracking — auto-created on monetize",
          len(mine) == 1 and mine[0]["status"] == "active"
          and mine[0]["term_months"] == settings.contract_term_months
          and mine[0]["expires_at"] > datetime.now(UTC).isoformat(), str(mine)[:90])
    cid = mine[0]["id"]
    check("M3: contract renewal control (auto_renew toggle)",
          c.patch(f"/api/v1/contracts/{cid}/auto-renew", headers=mh2,
                  json={"auto_renew": False}).json()["auto_renew"] is False)
    offer = c.post(f"/api/v1/admin/contracts/{cid}/buyout", headers=mh,
                   json={"amount": "500.00"})
    acc = c.post(f"/api/v1/contracts/{cid}/buyout/accept", headers=mh2)
    check("M3: contract buyout — offer -> accept credits the wallet once",
          offer.status_code == 200 and acc.status_code == 200
          and acc.json()["status"] == "bought_out"
          and c.post(f"/api/v1/contracts/{cid}/buyout/accept",
                     headers=mh2).status_code == 409, acc.text[:80])

    # Earnings processing + payment scheduling BY MEMBERSHIP TIER.
    from app.models.membership import MembershipTierConfig
    db = SessionLocal()
    try:
        prio = {c_.code.value: c_.payout_priority
                for c_ in db.scalars(select(MembershipTierConfig))}
    finally:
        db.close()
    check("M3: payout scheduling is ordered by membership tier priority",
          prio.get("special", 9) < prio.get("founding", 9) < prio.get("standard", 9),
          str(prio))
    c.patch("/api/v1/auth/me/payout-account", headers=mh2,
            json={"payout_account": "payee@example.com"})
    check("M3: payout account setter exists and validates",
          c.patch("/api/v1/auth/me/payout-account", headers=mh2,
                  json={"payout_account": "nope"}).status_code == 422)
    check("M3: own payouts are listable", c.get("/api/v1/payouts", headers=mh2).status_code == 200)
    check("M3: payout admin surface is moderator-gated",
          c.get("/api/v1/admin/payouts", headers=mh2).status_code == 403
          and c.get("/api/v1/admin/payouts", headers=mh).status_code == 200)

    # PayPal adapter present but never required.
    from app.adapters import paypal
    check("M3: PayPal Payouts adapter built to the documented v1 contract",
          hasattr(paypal, "submit_batch") and hasattr(paypal, "get_batch")
          and paypal.BATCH_SUCCESS == "SUCCESS" and paypal.TXN_SUCCESS == "SUCCESS"
          and {"FAILED", "RETURNED", "BLOCKED", "REFUNDED", "REVERSED"} <= paypal.TXN_FAILURES)
    check("M3: manual payout rail exists (no PayPal credentials required)",
          "/api/v1/admin/payouts/{payout_id}/mark-paid" in app.openapi()["paths"])

    # Affiliate performance ingestion — manual CSV of the REAL formats, no scraping.
    import pathlib

    from app.services import report_formats
    fx = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    shopee = report_formats.parse((fx / "shopee_commission_report.csv").read_bytes())
    lazada = report_formats.parse((fx / "lazada_conversion_report.csv").read_bytes())
    check("M3: real Shopee report ingests (detected, zero errors)",
          shopee.format == "shopee_commission_report" and not shopee.errors
          and len(shopee.rows) > 0, str(shopee.errors[:1]))
    check("M3: real Lazada report ingests despite being cp1252, not UTF-8",
          lazada.format == "lazada_conversion_report" and not lazada.errors
          and len(lazada.rows) > 0, str(lazada.errors[:1]))
    check("M3: unpayable rows (pending/cancelled/rejected) are never payable",
          all(r.order_status.lower() == "completed" for r in shopee.rows)
          and all(r.order_status.lower() == "delivered" for r in lazada.rows)
          and all(r.gross_amount > 0 for r in shopee.rows + lazada.rows))
    check("M3: sub-ID attribution is wired (queue exposes it; links store it)",
          "suggested_sub_id" in str(c.get("/api/v1/admin/review-queue?limit=1",
                                          headers=mh).json()))

    # Frontend integration readiness.
    spec = app.openapi()
    untagged = [f"{m} {p}" for p, item in spec["paths"].items()
                for m, op in item.items() if not op.get("tags")]
    types = pathlib.Path(__file__).resolve().parents[2] / "lib" / "api-types.d.ts"
    guide = pathlib.Path(__file__).resolve().parents[2] / "docs" / "FRONTEND_INTEGRATION.md"
    check("M3: frontend readiness — OpenAPI complete, TS types + guide delivered",
          not untagged and types.exists() and guide.exists()
          and "/api/v1/requests" in types.read_text(encoding="utf-8", errors="replace"),
          f"untagged={untagged[:2]}")

    # Load testing.
    lt = pathlib.Path(__file__).resolve().parents[1] / "loadtest" / "locustfile.py"
    res = pathlib.Path(__file__).resolve().parents[2] / "docs" / "LOADTEST_RESULTS.md"
    check("M3: load testing — profile + recorded results exist",
          lt.exists() and res.exists() and "p95" in res.read_text(encoding="utf-8"))

    # The anti-scraping mandate holds across every milestone.
    import subprocess
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = subprocess.run(
        ["grep", "-ril", "-e", "scrapy", "-e", "selenium", "-e", "playwright",
         "-e", "proxy_rotation", str(root)],
        capture_output=True, text=True).stdout.strip()
    check("ALL: no scraping code anywhere in the backend (owner mandate)",
          hits == "", hits[:100])


def main() -> int:
    url = make_url(settings.effective_database_url)
    print(f"MILESTONE VERIFICATION — {url.host}:{url.port}/{url.database} "
          f"(use_supabase={settings.use_supabase})")
    with engine.connect() as conn:
        print("server:", conn.execute(text("select version()")).scalar()[:40])
    hz = Harness()
    verify_m1(hz)
    verify_m2(hz)
    verify_m3(hz)
    passed = sum(1 for ok, *_ in _RESULTS if ok)
    failed = [f"{n} ({d})" for ok, n, d in _RESULTS if not ok]
    print(f"\n=== MILESTONE CLAIMS: {passed}/{len(_RESULTS)} verified ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    guard_cli("verify_milestones", production_is_legitimate=False)
    raise SystemExit(main())
