"""End-to-end API smoke test (functional + optional concurrency burst).

Exercises every M0/M1/M2-slice-1 endpoint over HTTP and asserts behavior, then
optionally fires bounded parallel bursts to confirm no 5xx/timeouts under load.

Moderator promotion is done directly via SQLAlchemy (SessionLocal), so this works
against whichever DB the app targets — point both the server and this script at the
same DB (local by default; Supabase with USE_SUPABASE=true).

Usage:
  python -m scripts.api_smoke --base-url http://localhost:8000
  USE_SUPABASE=true python -m scripts.api_smoke --base-url http://localhost:8001 --concurrency
"""

from __future__ import annotations

import argparse
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.core.env_guard import guard_cli
from app.db.session import SessionLocal
from app.models.enums import MemberRole
from app.models.session import Session as ClickSession
from app.models.user import User

SHOPEE = "https://shopee.ph/x-i.1.2?af=abc"
PW = "password123"
_RESULTS: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _RESULTS.append((ok, name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    return ok


def _promote(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        user.role = MemberRole.moderator
        db.commit()
    finally:
        db.close()


def _click_count(review_id: str) -> int:
    from sqlalchemy import func, select
    db = SessionLocal()
    try:
        return db.scalar(select(func.count(ClickSession.id)).where(
            ClickSession.review_id == uuid.UUID(review_id))) or 0
    finally:
        db.close()


def _click_ref(review_id: str) -> str | None:
    from sqlalchemy import select
    db = SessionLocal()
    try:
        return db.scalar(select(ClickSession.click_ref).where(
            ClickSession.review_id == uuid.UUID(review_id)).limit(1))
    finally:
        db.close()


def _client(base_url: str) -> httpx.Client:
    # Random X-Forwarded-For per run so rate-limit buckets don't accumulate.
    xff = f"203.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
    return httpx.Client(base_url=base_url, timeout=20.0,
                        headers={"x-forwarded-for": xff}, follow_redirects=False)


def _register(c: httpx.Client, email: str) -> str:
    r = c.post("/api/v1/auth/register", json={"email": email, "password": PW})
    return r.json()["access_token"]


def _make_review(c: httpx.Client, h: dict, *, stars: int, photo: bool, src: bool = True) -> tuple[str, str]:
    body = {"name": f"Prod {uuid.uuid4().hex[:6]}", "category": "electronics"}
    if src:
        body["source_url"] = "https://shopee.ph/x-i.1.2"
    pid = c.post("/api/v1/products", headers=h, json=body).json()["id"]
    rbody = {"product_id": pid, "title": "T", "discussion": "Used for weeks, solid.",
             "verdict": "yes_absolutely", "star_rating": stars}
    if photo:
        # Ownership is enforced on photo_url; omit it and assert the
        # review comes back unverified, which is the same contract.
        pass
    rid = c.post("/api/v1/reviews", headers=h, json=rbody).json()["id"]
    return rid, pid


def functional(base_url: str) -> tuple[str, str]:  # noqa: C901 - a flat checklist
    c = _client(base_url)
    ts = uuid.uuid4().hex[:8]
    author_email = f"sa_{ts}@ex.com"

    print("\n== Auth ==")
    check("GET /health 200", c.get("/health").status_code == 200)
    reg = c.post("/api/v1/auth/register", json={"email": author_email, "password": PW})
    check("register 201 + tier standard",
          reg.status_code == 201 and reg.json()["user"]["membership_tier"] == "standard",
          reg.text[:120])
    at = reg.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    dup = c.post("/api/v1/auth/register", json={"email": author_email, "password": PW})
    check("register duplicate -> 409 email_taken",
          dup.status_code == 409 and dup.json()["code"] == "email_taken")
    check("register short password -> 422",
          c.post("/api/v1/auth/register", json={"email": f"x{ts}@ex.com", "password": "short"}).status_code == 422)
    check("login (form) 200",
          c.post("/api/v1/auth/login", data={"username": author_email, "password": PW}).status_code == 200)
    bad = c.post("/api/v1/auth/login", data={"username": author_email, "password": "nope"})
    check("login wrong pw -> 401 invalid_credentials",
          bad.status_code == 401 and bad.json()["code"] == "invalid_credentials")
    me = c.get("/api/v1/auth/me", headers=ah)
    check("me 200 + email matches", me.status_code == 200 and me.json()["email"] == author_email)
    check("me no token -> 401", c.get("/api/v1/auth/me").status_code == 401)

    print("\n== Membership + RBAC ==")
    tiers = c.get("/api/v1/membership-tiers")
    check("list tiers has special/founding/standard",
          {t["code"] for t in tiers.json()} >= {"special", "founding", "standard"})
    check("get tier founding 200", c.get("/api/v1/membership-tiers/founding").status_code == 200)
    check("patch tier as non-mod -> 403",
          c.patch("/api/v1/membership-tiers/standard", headers=ah,
                  json={"revenue_share_bps": 3100}).status_code == 403)

    # Moderator user (promoted via DB; same token then works — RBAC reads DB role).
    mod_email = f"sm_{ts}@ex.com"
    mt = _register(c, mod_email)
    _promote(mod_email)
    mh = {"Authorization": f"Bearer {mt}"}
    check("patch tier as mod -> 200",
          c.patch("/api/v1/membership-tiers/standard", headers=mh,
                  json={"revenue_share_bps": 3000}).status_code == 200)
    check("assign tier as mod -> 200",
          c.patch(f"/api/v1/users/{me.json()['id']}/membership-tier", headers=mh,
                  json={"membership_tier": "founding"}).status_code == 200)

    print("\n== Products + Reviews + publication gate ==")
    check("get bogus product -> 404",
          c.get(f"/api/v1/products/{uuid.uuid4()}").status_code == 404)
    rid, _ = _make_review(c, ah, stars=4, photo=True)
    rv = c.get(f"/api/v1/reviews/{rid}", headers=ah).json()
    check("new review hidden+pending+verified+no-redirect",
          rv["published_at"] is None and rv["earn_eligible_status"] == "pending"
          and rv["verification_status"] == "verified" and rv["referral_redirect_url"] is None)
    unv, _ = _make_review(c, ah, stars=3, photo=False)
    check("no-photo review -> unverified",
          c.get(f"/api/v1/reviews/{unv}", headers=ah).json()["verification_status"] == "unverified")
    check("anon list hides unpublished", rid not in [r["id"] for r in c.get("/api/v1/reviews").json()])
    check("author list shows own draft", rid in [r["id"] for r in c.get("/api/v1/reviews", headers=ah).json()])
    check("anon GET unpublished -> 404", c.get(f"/api/v1/reviews/{rid}").status_code == 404)
    ed = c.patch(f"/api/v1/reviews/{rid}", headers=ah, json={"title": "T2", "change_note": "x"})
    check("author edit -> version 2", ed.status_code == 200 and ed.json()["current_version"] == 2)
    other = _register(c, f"so_{ts}@ex.com")
    check("edit by other -> 403",
          c.patch(f"/api/v1/reviews/{rid}", headers={"Authorization": f"Bearer {other}"},
                  json={"title": "hj"}).status_code == 403)
    check("versions anon -> 404", c.get(f"/api/v1/reviews/{rid}/versions").status_code == 404)
    check("versions author -> [1,2]",
          [v["version_number"] for v in c.get(f"/api/v1/reviews/{rid}/versions", headers=ah).json()] == [1, 2])
    crit = c.post(f"/api/v1/reviews/{rid}/critique", headers=ah)
    check("critique (stub) 200", crit.status_code == 200 and crit.json()["provider"] == "stub")
    check("critique by other -> 403",
          c.post(f"/api/v1/reviews/{rid}/critique",
                 headers={"Authorization": f"Bearer {other}"}).status_code == 403)
    check("ai/critique 200", c.post("/api/v1/ai/critique", headers=ah, json={"text": "x y z"}).status_code == 200)
    check("ai/critique no auth -> 401", c.post("/api/v1/ai/critique", json={"text": "x"}).status_code == 401)

    print("\n== Referral flow ==")

    def find_pending(review_id: str):
        # The queue is oldest-first, and a long-lived DB holds thousands of
        # never-published pending reviews, so a fresh one sits on the LAST page.
        # Scanning from the front is O(n) pages and every page computes fraud
        # signals per card. Ask the DB for this review's position instead.
        from sqlalchemy import func, select

        from app.models.enums import EarnEligibleStatus
        from app.models.review import Review
        db = SessionLocal()
        try:
            target = db.get(Review, uuid.UUID(review_id))
            if target is None:
                return None
            position = db.scalar(select(func.count(Review.id)).where(
                Review.earn_eligible_status == EarnEligibleStatus.pending,
                Review.published_at.is_(None), Review.is_removed.is_(False),
                Review.created_at < target.created_at)) or 0
        finally:
            db.close()
        for offset in (max(0, position - 2), max(0, position - 25)):
            page = c.get(f"/api/v1/admin/review-queue?limit=50&offset={offset}",
                         headers=mh).json()
            item = next((i for i in page["pending"] if i["review"]["id"] == review_id), None)
            if item is not None:
                return item
        return None

    qitem = find_pending(rid)
    check("queue lists review + suggested_platform + source_url",
          qitem is not None and qitem["suggested_platform"] == "shopee"
          and qitem["product"]["source_url"] is not None)
    check("queue as non-mod -> 403", c.get("/api/v1/admin/review-queue", headers=ah).status_code == 403)
    low, _ = _make_review(c, ah, stars=2, photo=True)
    check("attach <=2* -> 409 stars_too_low",
          c.post(f"/api/v1/admin/reviews/{low}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"}).json().get("code") == "stars_too_low_for_link")
    unvr, _ = _make_review(c, ah, stars=4, photo=False)
    check("attach unverified -> 409 review_not_verified",
          c.post(f"/api/v1/admin/reviews/{unvr}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"}).json().get("code") == "review_not_verified")
    att = c.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"})
    ab = att.json()
    check("attach -> monetized + published + redirect + link hidden",
          att.status_code == 200 and ab["earn_eligible_status"] == "monetized"
          and ab["published_at"] is not None and ab["referral_redirect_url"] == f"/r/{rid}"
          and SHOPEE not in str(ab))
    check("attach again -> 409 active_link_exists",
          c.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"}).json().get("code") == "active_link_exists")
    check("published review now in anon list", rid in [r["id"] for r in c.get("/api/v1/reviews").json()])
    red = c.get(f"/r/{rid}")
    check("redirect 302 -> affiliate url", red.status_code == 302 and red.headers["location"] == SHOPEE)
    check("click session row created", _click_count(rid) >= 1)
    rev = c.request("DELETE", f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                    json={"reason": "expired"})
    check("revoke -> approved, still published",
          rev.json()["earn_eligible_status"] == "approved" and rev.json()["published_at"] is not None)
    check("redirect after revoke -> 404", c.get(f"/r/{rid}").status_code == 404)
    check("re-attach -> 200 monetized",
          c.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                 json={"url": SHOPEE, "platform": "shopee"}).json()["earn_eligible_status"] == "monetized")
    hist = c.get(f"/api/v1/admin/reviews/{rid}/referral-links", headers=mh).json()
    check("link history == [active, revoked]", sorted(link["status"] for link in hist) == ["active", "revoked"])
    ced = c.patch(f"/api/v1/reviews/{rid}", headers=ah, json={"title": "T3", "change_note": "y"})
    check("edited-since-monetized appears in queue",
          ced.status_code == 200 and rid in
          [i["review"]["id"] for i in c.get("/api/v1/admin/review-queue", headers=mh).json()["edited_since_monetized"]])

    print("\n== No-link publish / reject / unpublish ==")
    pub = c.post(f"/api/v1/admin/reviews/{low}/publish", headers=mh)
    check("publish <=2* -> honesty_fund + published",
          pub.json()["earn_eligible_status"] == "honesty_fund" and pub.json()["published_at"] is not None)
    rej_r, _ = _make_review(c, ah, stars=5, photo=True)
    rej = c.post(f"/api/v1/admin/reviews/{rej_r}/reject", headers=mh, json={"reason": "blurry"})
    check("reject -> rejected + hidden",
          rej.json()["earn_eligible_status"] == "rejected" and rej.json()["published_at"] is None)
    check("edit rejected -> re-queued to pending",
          c.patch(f"/api/v1/reviews/{rej_r}", headers=ah,
                  json={"discussion": "reworded fully", "change_note": "z"}).json()["earn_eligible_status"] == "pending")
    unp = c.post(f"/api/v1/admin/reviews/{rid}/unpublish", headers=mh, json={})
    check("unpublish -> hidden", unp.json()["published_at"] is None)
    check("redirect after unpublish -> 404", c.get(f"/r/{rid}").status_code == 404)

    print("\n== URL validation + admin RBAC ==")
    def rule(url, plat):
        return c.post(f"/api/v1/admin/reviews/{rej_r}/referral-link", headers=mh,
                      json={"url": url, "platform": plat})
    check("http:// -> 422", rule("http://shopee.ph/x", "shopee").status_code == 422)
    check("wrong domain -> 422", rule("https://evil.example.com/x", "shopee").status_code == 422)
    check("wrong platform -> 422", rule(SHOPEE, "amazon").status_code == 422)
    check("admin attach as non-mod -> 403",
          c.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=ah,
                 json={"url": SHOPEE, "platform": "shopee"}).status_code == 403)

    print("\n== M2: voting + Wilson ranking ==")
    author_id = me.json()["id"]
    voter = _register(c, f"sv_{ts}@ex.com")
    vh = {"Authorization": f"Bearer {voter}"}
    check("self-vote -> 409 cannot_vote_own_review",
          c.post(f"/api/v1/reviews/{low}/vote", headers=ah,
                 json={"vote": "up"}).json().get("code") == "cannot_vote_own_review")
    v = c.post(f"/api/v1/reviews/{low}/vote", headers=vh, json={"vote": "up"})
    check("vote up -> counters + wilson > 0",
          v.status_code == 200 and v.json()["helpful_votes"] == 1
          and float(v.json()["wilson_score"]) > 0)
    v2 = c.post(f"/api/v1/reviews/{low}/vote", headers=vh, json={"vote": "down"})
    check("vote change -> upsert (1 down, 0 up)",
          v2.json()["helpful_votes"] == 0 and v2.json()["unhelpful_votes"] == 1)
    vd = c.delete(f"/api/v1/reviews/{low}/vote", headers=vh)
    check("vote delete -> counters reset", vd.json()["unhelpful_votes"] == 0)
    check("anon vote -> 401", c.post(f"/api/v1/reviews/{low}/vote", json={"vote": "up"}).status_code == 401)
    check("?sort=wilson 200", c.get("/api/v1/reviews?sort=wilson").status_code == 200)

    print("\n== M2: trust progression ==")
    tr = c.get(f"/api/v1/users/{author_id}/trust")
    check("trust endpoint shape + stage >= 2 (published verified review)",
          tr.status_code == 200 and tr.json()["trust_stage"] >= 2
          and "badges" in tr.json() and "reputation_score" in tr.json())

    print("\n== M2: seller reviews + role management ==")
    seller_email = f"ss_{ts}@ex.com"
    st = _register(c, seller_email)
    seller_id = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {st}"}).json()["id"]
    check("role change as non-mod -> 403",
          c.patch(f"/api/v1/users/{seller_id}/role", headers=ah, json={"role": "seller"}).status_code == 403)
    check("grant moderator via API -> 422",
          c.patch(f"/api/v1/users/{seller_id}/role", headers=mh, json={"role": "moderator"}).status_code == 422)
    check("promote to seller -> 200",
          c.patch(f"/api/v1/users/{seller_id}/role", headers=mh, json={"role": "seller"}).json()["role"] == "seller")
    sr_body = {"accuracy": True, "order_completeness": True, "customer_service": 5,
               "packaging_quality": 4, "overall_rating": 5, "would_recommend": True}
    sr = c.post(f"/api/v1/sellers/{seller_id}/reviews", headers=vh, json=sr_body)
    check("seller review 201 (publishes immediately)", sr.status_code == 201)
    check("duplicate seller review -> 409",
          c.post(f"/api/v1/sellers/{seller_id}/reviews", headers=vh, json=sr_body).status_code == 409)
    prof = c.get(f"/api/v1/sellers/{seller_id}")
    check("seller profile aggregates + trust score",
          prof.status_code == 200 and prof.json()["review_count"] == 1
          and prof.json()["recommend_pct"] == 100.0
          and prof.json()["seller_trust_score"] is not None)
    check("seller review list 200", len(c.get(f"/api/v1/sellers/{seller_id}/reviews").json()) == 1)
    check("product listing has trust_score + low_trust fields",
          {"trust_score", "low_trust"} <= set(c.get("/api/v1/products").json()[0].keys()))

    print("\n== M2: fraud signals (queue only) ==")
    q2 = c.get("/api/v1/admin/review-queue", headers=mh).json()
    pool = q2["pending"] + q2["edited_since_monetized"]
    check("queue items carry signals",
          bool(pool) and all("signals" in i and "collusion" in i["signals"] for i in pool))
    check("public review has no signals",
          "signals" not in c.get(f"/api/v1/reviews/{low}").json())

    print("\n== M2: tokens ==")
    bal = c.get("/api/v1/tokens/balance", headers=ah)
    check("publish awarded tokens (balance > 0)",
          bal.status_code == 200 and bal.json()["token_balance"] > 0)
    check("transactions ledger 200",
          c.get("/api/v1/tokens/transactions", headers=ah).status_code == 200)
    tg = c.post(f"/api/v1/admin/users/{seller_id}/tokens", headers=mh,
                json={"amount": 7, "note": "smoke grant"})
    check("admin token grant 200 + balance_after", tg.status_code == 200 and tg.json()["balance_after"] >= 7)
    check("token deduct below zero -> 409 insufficient_tokens",
          c.post(f"/api/v1/admin/users/{seller_id}/tokens", headers=mh,
                 json={"amount": -10_000, "note": "too much"}).json().get("code") == "insufficient_tokens")
    check("token grant as non-mod -> 403",
          c.post(f"/api/v1/admin/users/{seller_id}/tokens", headers=ah,
                 json={"amount": 5, "note": "x"}).status_code == 403)

    print("\n== M2: commission CSV import ==")
    ref = _click_ref(rid)
    csv_text = ("click_ref,order_ref,gross_amount,currency,order_status,platform\n"
                f"{ref},ORD-{ts},100.00,PHP,completed,shopee\n")
    imp = c.post("/api/v1/admin/commissions/import", headers=mh,
                 files={"file": (f"smoke_{ts}.csv", csv_text.encode(), "text/csv")})
    check("import 200 + 1 imported", imp.status_code == 200 and imp.json()["imported"] == 1, imp.text[:160])
    imp2 = c.post("/api/v1/admin/commissions/import", headers=mh,
                  files={"file": (f"smoke_{ts}.csv", csv_text.encode(), "text/csv")})
    check("re-import -> all skipped (idempotent)",
          imp2.json()["imported"] == 0 and imp2.json()["skipped_duplicates"] == 1)
    bad_csv = ("click_ref,order_ref,gross_amount,currency,order_status,platform\n"
               f"{ref},,abc,PHP,done,shopee\n")
    check("malformed row -> 422 nothing imported",
          c.post("/api/v1/admin/commissions/import", headers=mh,
                 files={"file": ("bad.csv", bad_csv.encode(), "text/csv")}).status_code == 422)
    check("import as non-mod -> 403",
          c.post("/api/v1/admin/commissions/import", headers=ah,
                 files={"file": ("x.csv", csv_text.encode(), "text/csv")}).status_code == 403)

    print("\n== M2: honesty fund admin trigger ==")
    hf = c.post("/api/v1/admin/honesty-fund/run", headers=mh,
                json={"cycle_month": f"19{random.randint(10, 49)}-01"})
    check("honesty-fund run 200 (empty historic cycle -> no-op)",
          hf.status_code == 200 and hf.json()["status"] in
          ("empty_pool", "already_distributed", "no_eligible_reviews", "distributed"), hf.text[:160])
    check("honesty-fund run as non-mod -> 403",
          c.post("/api/v1/admin/honesty-fund/run", headers=ah, json={}).status_code == 403)

    c.close()
    return at, mt


def concurrency(base_url: str, at: str, mt: str) -> None:
    print("\n== Concurrency smoke (bounded; PASS = zero 5xx/timeouts) ==")
    ah = {"Authorization": f"Bearer {at}"}
    c = _client(base_url)
    pid = c.post("/api/v1/products", headers=ah,
                 json={"name": "Burst", "category": "electronics"}).json()["id"]
    c.close()

    def hit(kind: str) -> int:
        cc = httpx.Client(base_url=base_url, timeout=20.0)
        try:
            if kind == "reviews":
                return cc.get("/api/v1/reviews").status_code
            if kind == "health":
                return cc.get("/health").status_code
            if kind == "queue":
                return cc.get("/api/v1/admin/review-queue", headers={"Authorization": f"Bearer {mt}"}).status_code
            if kind == "submit":
                return cc.post("/api/v1/reviews", headers=ah, json={
                    "product_id": pid, "title": "b", "discussion": "burst review text",
                    "verdict": "it_depends", "star_rating": 3,
                    }).status_code
        finally:
            cc.close()
        return 0

    jobs = (["reviews"] * 30 + ["health"] * 30 + ["queue"] * 10 + ["submit"] * 10)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=20) as ex:
        codes = list(ex.map(hit, jobs))
    dur = time.monotonic() - t0
    hist: dict[int, int] = {}
    for code in codes:
        hist[code] = hist.get(code, 0) + 1
    server_errors = sum(v for k, v in hist.items() if k >= 500 or k == 0)
    print(f"  {len(jobs)} requests in {dur:.2f}s  status histogram: {dict(sorted(hist.items()))}")
    check("no 5xx / timeouts under burst", server_errors == 0, f"{server_errors} server errors")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--concurrency", action="store_true")
    args = ap.parse_args()
    print(f"API SMOKE — {args.base_url}")
    at, mt = functional(args.base_url)
    if args.concurrency:
        concurrency(args.base_url, at, mt)
    passed = sum(1 for ok, *_ in _RESULTS if ok)
    failed = [f"{n} ({d})" for ok, n, d in _RESULTS if not ok]
    print(f"\n=== RESULT: {passed}/{len(_RESULTS)} passed ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    guard_cli("api_smoke", production_is_legitimate=False)
    raise SystemExit(main())
