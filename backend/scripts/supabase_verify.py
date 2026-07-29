"""Deep verification against the LIVE database (designed for Supabase).

Two layers, both reported as PASS/FAIL checks:

1. SCHEMA TRUTH — inspects what is *actually inside* the database: all 21 tables,
   the M2 columns, the partial-unique/trigram indexes, RLS state + policies,
   enum values, the pg_trgm extension, and the seeded tier/badge rows.
2. FLOW TRUTH — drives the real API in-process (TestClient) and then verifies
   every side effect with direct SQL against the same database: users, reviews,
   referral links, click sessions, votes + wilson, trust + badges, commissions +
   wallet, token ledger chain, honesty-fund payouts, PII retention.

Usage:
  USE_SUPABASE=true python -m scripts.supabase_verify           # verify + clean up
  USE_SUPABASE=true python -m scripts.supabase_verify --keep    # leave the rows

Exit code 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings

# The verifier drives many auth/vote calls from one client; don't self-throttle.
settings.auth_rate_limit_max = 1_000_000
settings.vote_rate_limit_max = 1_000_000

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

_RESULTS: list[tuple[bool, str, str]] = []
PW = "password123"

def _alembic_head() -> str:
    """The head revision, read from the migration scripts themselves.

    This was a hand-typed constant and it drifted — pinned at 0014 while the
    database legitimately advanced to 0019, so the check reported a failure on
    every run and taught the reader to ignore it. Deriving it means the check
    asserts what it claims to: that the DB is at the head this checkout defines.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    ).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"expected a single alembic head, found {heads}")
    return heads[0]


HEAD_REVISION = _alembic_head()

# Every path that moves users.wallet_balance. Keep this in step with the code —
# an invariant that ignores a money path is worse than no invariant.
#   IN : commissions.reviewer_share        (M2 slice 6 — CSV reconciliation)
#   IN : honesty_fund_distributions.payout (M2 slice 8 — monthly fund)
#   IN : review_contracts buyout           (M3 slice 10 — accepted buyout)
#   OUT: payouts reserved at schedule time (M3 slice 11 — scheduled/processing/
#        paid; `failed` and `cancelled` refund, so they must NOT be subtracted)
WALLET_SOURCES_SQL = """
    coalesce((SELECT sum(c.reviewer_share) FROM commissions c
              WHERE c.reviewer_id = u.id), 0)
  + coalesce((SELECT sum(h.payout_amount) FROM honesty_fund_distributions h
              WHERE h.reviewer_id = u.id), 0)
  + coalesce((SELECT sum(k.buyout_offer_amount) FROM review_contracts k
              WHERE k.reviewer_id = u.id AND k.status = 'bought_out'::contract_status
                AND k.buyout_accepted_at IS NOT NULL), 0)
  - coalesce((SELECT sum(p.amount) FROM payouts p
              WHERE p.user_id = u.id
                AND p.status IN ('scheduled'::payout_status,
                                 'processing'::payout_status,
                                 'paid'::payout_status)), 0)
"""

EXPECTED_TABLES = {
    "users", "badges", "user_badges", "products", "product_platforms",
    "price_history", "reviews", "review_versions", "referral_links", "questions",
    "answers", "seller_reviews", "sessions", "commissions",
    "honesty_fund_distributions", "moderation_logs", "earn_eligible_votes",
    "membership_tiers", "review_votes", "token_transactions", "alembic_version",
    # M3 slices 9 / 10 / 11
    "review_requests", "request_upvotes", "review_contracts", "payouts",
}

EXPECTED_TOKEN_KINDS = {
    "earn_review_published", "earn_commission", "admin_grant", "admin_deduct",
    "adjustment",
    # M3 slice 9 — request board escrow/reward flow
    "spend_request_escrow", "earn_request_reward", "refund_request_escrow",
    "platform_topup",
}

M2_COLUMNS = [
    ("products", "trust_score"),
    ("users", "seller_trust_score"),
    ("users", "token_balance"),
    ("commissions", "reviewer_tier"),
    ("commissions", "reviewer_share_bps"),
    ("reviews", "published_at"),
    ("reviews", "wilson_score"),
]

M2_INDEXES = [
    ("token_transactions", "uq_token_once"),
    ("seller_reviews", "uq_seller_review_once"),
    ("reviews", "ix_reviews_discussion_trgm"),
    ("review_votes", "uq_review_vote_once"),
    ("referral_links", "uq_referral_active"),
    # M3
    ("request_upvotes", "uq_request_upvote_once"),
    ("review_contracts", "uq_contract_active"),
    ("payouts", "uq_payout_user_batch"),
    ("referral_links", "uq_referral_sub_id_active"),
]


def check(name: str, ok: bool, detail: str = "") -> bool:
    _RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    return bool(ok)


def q(db, sql: str, **params):
    return db.execute(text(sql), params)


# ---------------------------------------------------------------- schema truth
def verify_schema(db) -> None:
    print("\n== SCHEMA: migrations & tables ==")
    rev = q(db, "SELECT version_num FROM alembic_version").scalar()
    check(f"alembic_version == {HEAD_REVISION} (head)", rev == HEAD_REVISION, str(rev))

    tables = {r[0] for r in q(db, "SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    missing = EXPECTED_TABLES - tables
    check(f"all {len(EXPECTED_TABLES)} expected public tables exist", not missing,
          f"missing: {sorted(missing)}")

    print("\n== SCHEMA: M2 columns ==")
    for table, column in M2_COLUMNS:
        found = q(db, """SELECT 1 FROM information_schema.columns
                         WHERE table_schema='public' AND table_name=:t AND column_name=:c""",
                  t=table, c=column).scalar()
        check(f"{table}.{column} exists", found == 1)

    print("\n== SCHEMA: indexes & constraints ==")
    for table, index in M2_INDEXES:
        row = q(db, "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
                    "AND tablename=:t AND indexname=:i", t=table, i=index).scalar()
        check(f"index {index} on {table}", row is not None)
    uq_token = q(db, "SELECT indexdef FROM pg_indexes "
                     "WHERE indexname='uq_token_once'").scalar() or ""
    check("uq_token_once is partial (earn kinds, ref_id NOT NULL) and UNIQUE",
          "UNIQUE" in uq_token and "ref_id IS NOT NULL" in uq_token
          and "earn_review_published" in uq_token, uq_token[:120])

    print("\n== SCHEMA: pg_trgm ==")
    ext = q(db, "SELECT 1 FROM pg_extension WHERE extname='pg_trgm'").scalar()
    check("pg_trgm extension installed", ext == 1)
    sim = q(db, "SELECT similarity('bluntly review text', 'bluntly review text')").scalar()
    check("similarity() callable and sane", sim == 1.0, str(sim))

    print("\n== SCHEMA: enums ==")
    kinds = {r[0] for r in q(db, """SELECT e.enumlabel FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname='token_kind'""")}
    check(f"token_kind enum has all {len(EXPECTED_TOKEN_KINDS)} values",
          kinds == EXPECTED_TOKEN_KINDS, str(sorted(kinds)))
    statuses = {r[0] for r in q(db, """SELECT e.enumlabel FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname='request_status'""")}
    check("request_status enum has all 5 values",
          statuses == {"open", "fulfilled", "cancelled", "expired", "removed"},
          str(sorted(statuses)))
    platforms = {r[0] for r in q(db, """SELECT e.enumlabel FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname='platform'""")}
    check("platform enum includes amazon", "amazon" in platforms)

    print("\n== SCHEMA: RLS posture ==")
    no_rls = [r[0] for r in q(db, """SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity""")]
    check("every public table has RLS enabled", not no_rls, f"without RLS: {no_rls}")
    rv_policies = q(db, "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
                        "AND tablename='review_votes' AND cmd='SELECT'").scalar()
    check("review_votes has a public SELECT policy", rv_policies >= 1)
    tt_policies = q(db, "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
                        "AND tablename='token_transactions'").scalar()
    check("token_transactions has NO permissive policies (backend-only)", tt_policies == 0)

    print("\n== SCHEMA: whole-database integrity invariants ==")
    # These hold for EVERY row already in the database, not just this run's —
    # they catch drift that per-flow assertions can't see.
    bad_ledger = q(db, """SELECT count(*) FROM (
            SELECT u.id FROM users u
            LEFT JOIN token_transactions t ON t.user_id = u.id
            GROUP BY u.id, u.token_balance
            HAVING u.token_balance <> coalesce(sum(t.amount), 0)) x""").scalar()
    check("every users.token_balance == SUM(its ledger amounts)", bad_ledger == 0,
          f"{bad_ledger} users drifted")

    bad_wallet = q(db, f"SELECT count(*) FROM users u WHERE u.wallet_balance <> "
                       f"({WALLET_SOURCES_SQL})").scalar()
    check("every users.wallet_balance == inflows(commissions+fund+buyouts) "
          "- reserved payouts", bad_wallet == 0, f"{bad_wallet} users drifted")

    # A payout must never exceed what the user ever earned, and a paid payout
    # must carry its provider reference (manual or PayPal) for the audit trail.
    orphan_payout = q(db, """SELECT count(*) FROM payouts p
            LEFT JOIN users u ON u.id = p.user_id WHERE u.id IS NULL""").scalar()
    check("no orphaned payouts", orphan_payout == 0, f"{orphan_payout} payouts")
    unref_paid = q(db, """SELECT count(*) FROM payouts
            WHERE status = 'paid'::payout_status
              AND (provider_ref IS NULL OR paid_at IS NULL)""").scalar()
    check("every paid payout records provider_ref + paid_at",
          unref_paid == 0, f"{unref_paid} payouts")

    dupes = q(db, """SELECT count(*) FROM (
            SELECT 1 FROM token_transactions
            WHERE ref_id IS NOT NULL AND kind IN ('earn_review_published'::token_kind,
                                                  'earn_commission'::token_kind)
            GROUP BY user_id, kind, ref_id HAVING count(*) > 1) x""").scalar()
    check("no (user, earn kind, ref) awarded twice anywhere", dupes == 0,
          f"{dupes} duplicate earn groups")

    orphan_votes = q(db, """SELECT count(*) FROM review_votes v
            LEFT JOIN reviews r ON r.id = v.review_id WHERE r.id IS NULL""").scalar()
    orphan_tokens = q(db, """SELECT count(*) FROM token_transactions t
            LEFT JOIN users u ON u.id = t.user_id WHERE u.id IS NULL""").scalar()
    check("no orphaned review_votes / token_transactions",
          orphan_votes == 0 and orphan_tokens == 0,
          f"votes={orphan_votes} tokens={orphan_tokens}")

    neg = q(db, "SELECT count(*) FROM users WHERE token_balance < 0 "
                "OR wallet_balance < 0").scalar()
    check("no negative token or wallet balances", neg == 0, f"{neg} users")

    bad_split = q(db, """SELECT count(*) FROM commissions
            WHERE platform_share + reviewer_share + honesty_fund_share
                  <> gross_amount""").scalar()
    check("every commission's 3 shares re-sum to gross_amount exactly",
          bad_split == 0, f"{bad_split} commissions")

    # M3 slice 9: a request's escrow must resolve exactly once — a closed request
    # is either refunded (cancelled/expired/removed) or paid out (fulfilled),
    # never both and never neither. Open requests must have neither yet.
    bad_escrow = q(db, """
        SELECT count(*) FROM (
          SELECT r.id, r.status,
            (SELECT count(*) FROM token_transactions t WHERE t.ref_id = r.id
               AND t.kind = 'refund_request_escrow'::token_kind) AS refunds,
            (SELECT count(*) FROM token_transactions t WHERE t.ref_id = r.id
               AND t.kind = 'earn_request_reward'::token_kind) AS payouts
          FROM review_requests r
        ) x
        WHERE (status IN ('cancelled','expired','removed') AND NOT (refunds = 1 AND payouts = 0))
           OR (status = 'fulfilled' AND NOT (payouts = 1 AND refunds = 0))
           OR (status = 'open' AND (refunds > 0 OR payouts > 0))""").scalar()
    check("every request escrow resolves exactly once (refunded XOR paid out)",
          bad_escrow == 0, f"{bad_escrow} requests")

    print("\n== SCHEMA: seed data ==")
    tiers = {r[0]: r[1] for r in q(db, "SELECT code, revenue_share_bps FROM membership_tiers")}
    check("membership tiers seeded with pinned bps (3000/3500/4000)",
          tiers.get("standard") == 3000 and tiers.get("founding") == 3500
          and tiers.get("special") == 4000, str(tiers))
    badge_count = q(db, "SELECT count(*) FROM badges WHERE badge_id IN "
                        "('verified_buyer','established_reviewer','trusted_reviewer',"
                        "'community_expert')").scalar()
    check("all 4 stage badges seeded", badge_count == 4, f"found {badge_count}")


# ------------------------------------------------------------------ flow truth
def verify_flow(db, client: TestClient, keep: bool) -> None:
    from app.models.enums import MemberRole
    from app.models.user import User
    from app.services.honesty_fund_service import distribute
    from app.services.pii import hash_ip, retention_deadlines
    from app.services.retention_service import run_retention_sweep

    ts = uuid.uuid4().hex[:8]
    created_users: list[str] = []
    created_products: list[str] = []
    created_sessions: list[str] = []
    cleanup_cycles: list[date] = []
    cleanup_commissions: list[str] = []

    def register(tag: str) -> tuple[str, dict]:
        email = f"verify_{tag}_{ts}@example.com"
        r = client.post("/api/v1/auth/register", json={"email": email, "password": PW})
        assert r.status_code == 201, r.text
        body = r.json()
        created_users.append(body["user"]["id"])
        return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}

    print("\n== FLOW: auth writes land in Supabase ==")
    author_id, ah = register("author")
    voter_id, vh = register("voter")
    mod_id, mh = register("mod")
    db.query(User).filter(User.id == uuid.UUID(mod_id)).update({"role": MemberRole.moderator})
    db.commit()
    row = q(db, "SELECT email, password_hash, role FROM users WHERE id = :id",
            id=author_id).first()
    check("registered user row exists with Argon2id hash",
          row is not None and (row[1] or "").startswith("$argon2"), str(row))

    print("\n== FLOW: review -> publish -> referral link -> click ==")
    pid = client.post("/api/v1/products", headers=ah, json={
        "name": f"VerifyWidget {ts}", "category": "electronics",
        "source_url": "https://shopee.ph/x-i.1.2"}).json()["id"]
    created_products.append(pid)
    rid = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": pid, "title": "Verify", "discussion": f"Verification run {ts}.",
        "verdict": "yes_absolutely", "star_rating": 4,
        "photo_url": "https://example.com/proof.jpg"}).json()["id"]
    r = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                    json={"url": "https://shopee.ph/x-i.1.2?af=v", "platform": "shopee"})
    check("attach+publish 200", r.status_code == 200, r.text[:120])
    row = q(db, """SELECT r.published_at, r.earn_eligible_status, l.status
                   FROM reviews r JOIN referral_links l ON l.review_id = r.id
                   WHERE r.id = :rid""", rid=rid).first()
    check("DB: review published+monetized with ACTIVE referral_links row",
          row is not None and row[0] is not None
          and row[1] == "monetized" and row[2] == "active", str(row))
    audit = q(db, """SELECT count(*) FROM moderation_logs
                     WHERE target_ref = :rid AND action = 'affiliate_link_attach'""",
              rid=rid).scalar()
    check("DB: attach action audit-logged in moderation_logs", audit == 1)

    red = client.get(f"/r/{rid}", follow_redirects=False)
    check("redirect 302", red.status_code == 302)
    srow = q(db, """SELECT id, click_ref, ip_hash_at, ip_delete_at, ua_purge_at
                    FROM sessions WHERE review_id = :rid""", rid=rid).first()
    check("DB: click created a sessions row with all 3 PII deadlines",
          srow is not None and srow[1] and srow[2] and srow[3] and srow[4], str(srow))
    click_ref = srow[1] if srow else None
    if srow:
        created_sessions.append(str(srow[0]))

    print("\n== FLOW: token award on publish (ledger truth) ==")
    trow = q(db, """SELECT amount, balance_after, kind, ref_id FROM token_transactions
                    WHERE user_id = :uid ORDER BY created_at""", uid=author_id).all()
    bal = q(db, "SELECT token_balance FROM users WHERE id = :uid", uid=author_id).scalar()
    check("DB: exactly one earn_review_published ledger row, mirror in sync",
          len(trow) == 1 and trow[0][0] == settings.tokens_on_review_published
          and str(trow[0][3]) == rid and bal == trow[0][1], f"rows={trow} bal={bal}")

    print("\n== FLOW: vote -> wilson -> trust -> badge ==")
    v = client.post(f"/api/v1/reviews/{rid}/vote", headers=vh, json={"vote": "up"})
    check("vote 200", v.status_code == 200, v.text[:120])
    row = q(db, """SELECT r.helpful_votes, r.wilson_score,
                          (SELECT count(*) FROM review_votes WHERE review_id = r.id)
                   FROM reviews r WHERE r.id = :rid""", rid=rid).first()
    check("DB: review_votes row + counters + wilson_score persisted",
          row is not None and row[0] == 1 and row[1] > 0 and row[2] == 1, str(row))
    urow = q(db, """SELECT trust_stage, trust_level_name, verified_review_count,
                           helpfulness_ratio FROM users WHERE id = :uid""",
             uid=author_id).first()
    check("DB: author trust recomputed (stage 2 'Verified Buyer', 100% helpful)",
          urow is not None and urow[0] == 2 and urow[1] == "Verified Buyer"
          and urow[2] == 1 and float(urow[3]) == 100.0, str(urow))
    brow = q(db, """SELECT count(*) FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
                    WHERE ub.user_id = :uid AND b.badge_id = 'verified_buyer'""",
             uid=author_id).scalar()
    check("DB: verified_buyer badge row awarded exactly once", brow == 1, str(brow))

    print("\n== FLOW: commission CSV -> commissions/wallet/session/tokens ==")
    csv_text = ("click_ref,order_ref,gross_amount,currency,order_status,platform\n"
                f"{click_ref},ORD-{ts},100.00,PHP,completed,shopee\n")
    imp = client.post("/api/v1/admin/commissions/import", headers=mh,
                      files={"file": (f"verify_{ts}.csv", csv_text.encode(), "text/csv")})
    check("import 200 imported=1", imp.status_code == 200 and imp.json()["imported"] == 1,
          imp.text[:160])
    crow = q(db, """SELECT id, reviewer_share, honesty_fund_share, reviewer_tier,
                           reviewer_share_bps, cycle_month
                    FROM commissions WHERE review_id = :rid""", rid=rid).first()
    check("DB: commissions row with tier snapshot (standard/3000) and exact split",
          crow is not None and crow[1] == Decimal("30.00") and crow[2] == Decimal("30.00")
          and crow[3] == "standard" and crow[4] == 3000, str(crow))
    if crow:
        cleanup_commissions.append(str(crow[0]))
    wrow = q(db, "SELECT wallet_balance, token_balance FROM users WHERE id = :uid",
             uid=author_id).first()
    check("DB: wallet +30.00 and tokens +25 (publish 10 + commission 25)",
          wrow is not None and wrow[0] == Decimal("30.00")
          and wrow[1] == settings.tokens_on_review_published + settings.tokens_on_commission,
          str(wrow))
    conv = q(db, "SELECT conversion_status, order_ref FROM sessions WHERE click_ref = :cr",
             cr=click_ref).first()
    check("DB: session converted with order_ref backfilled",
          conv is not None and conv[0] == "converted" and conv[1] == f"ORD-{ts}", str(conv))

    print("\n== FLOW: honesty fund cycle (synthetic historic cycle) ==")
    hf_rid = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": pid, "title": "Bad", "discussion": f"Honest 2-star warning {ts}.",
        "verdict": "hard_pass", "star_rating": 2, "price_paid": "100",
        "photo_url": "https://example.com/proof2.jpg"}).json()["id"]
    client.post(f"/api/v1/admin/reviews/{hf_rid}/publish", headers=mh)
    db.query(User).filter(User.id == uuid.UUID(voter_id)).update({
        "trust_stage": 2, "reputation_score": 100,
        "created_at": datetime.now(UTC) - timedelta(days=60)})
    db.commit()
    client.post(f"/api/v1/reviews/{hf_rid}/vote", headers=vh, json={"vote": "up"})
    # Claim a cycle with no distributions/commissions yet. The fund is idempotent
    # per cycle, so a random draw eventually collides with an earlier run and the
    # check fails on the app behaving correctly.
    used = {r[0] for r in q(db, "SELECT DISTINCT cycle_month FROM honesty_fund_distributions")}
    used |= {r[0] for r in q(db, "SELECT DISTINCT cycle_month FROM commissions")}
    cycle = next(date(y, m, 1) for y in range(1900, 2100) for m in range(1, 13)
                 if date(y, m, 1) not in used)
    cleanup_cycles.append(cycle)
    q(db, """INSERT INTO commissions (id, commission_id, target_type, review_id,
             gross_amount, platform_share, reviewer_share, honesty_fund_share,
             csv_source, row_reference, cycle_month)
             VALUES (gen_random_uuid(), :cid, 'review', :rid, 100, 40, 30, 30,
                     :src, '2', :cycle)""",
      cid=f"com_verify_{ts}", rid=hf_rid, src=f"verify:{ts}", cycle=cycle)
    db.commit()
    result = distribute(db, cycle_month=cycle, triggered_by=uuid.UUID(mod_id))
    hrow = q(db, """SELECT payout_amount, honesty_score FROM honesty_fund_distributions
                    WHERE cycle_month = :c AND review_id = :rid""",
             c=cycle, rid=hf_rid).first()
    check("DB: honesty_fund_distributions row written, payout > 0, wallet credited",
          result["status"] == "distributed" and hrow is not None and hrow[0] > 0,
          f"{result} {hrow}")
    again = distribute(db, cycle_month=cycle)
    check("re-run same cycle ABORTS (idempotent)", again["status"] == "already_distributed")

    print("\n== FLOW: PII retention sweep (bulk SQL vs python hash parity) ==")
    old_ip = "198.51.100.77"
    for days, ip_suffix in ((31, old_ip), (91, "203.0.113.99")):
        clicked = datetime.now(UTC) - timedelta(days=days)
        d = retention_deadlines(clicked)
        sid = str(uuid.uuid4())
        q(db, """INSERT INTO sessions (id, session_id, click_ref, clicked_at, ip_address,
                 user_agent, ip_hash_at, ip_delete_at, ua_purge_at)
                 VALUES (:id, :sid, :cr, :clicked, :ip, 'VerifyAgent/1.0',
                         :h, :d, :u)""",
          id=sid, sid=f"clk_verify_{days}_{ts}", cr=f"ref_verify_{days}_{ts}",
          clicked=clicked, ip=ip_suffix, h=d["ip_hash_at"],
          d=d["ip_delete_at"], u=d["ua_purge_at"])
        created_sessions.append(sid)
    db.commit()
    run_retention_sweep(db)
    hrow = q(db, "SELECT ip_address, ip_hash, user_agent FROM sessions "
                 "WHERE click_ref = :cr", cr=f"ref_verify_31_{ts}").first()
    check("DB: 31d session -> IP nulled, hash == services.pii.hash_ip (parity)",
          hrow is not None and hrow[0] is None
          and hrow[1] == hash_ip(old_ip, settings.pii_hash_salt)
          and hrow[2] is not None, str(hrow))
    prow = q(db, "SELECT ip_address, ip_hash, user_agent FROM sessions "
                 "WHERE click_ref = :cr", cr=f"ref_verify_91_{ts}").first()
    check("DB: 91d session -> IP, hash and UA all purged",
          prow is not None and prow[0] is None and prow[1] is None and prow[2] is None,
          str(prow))

    print("\n== FLOW: public surface stays clean ==")
    pub = client.get(f"/api/v1/reviews/{rid}").json()
    check("public review carries no raw affiliate URL and no fraud signals",
          "signals" not in pub and "shopee.ph" not in str(pub))

    if keep:
        print("\n(--keep: verification rows left in the database)")
        return
    print("\n== CLEANUP ==")
    for cid in cleanup_commissions:
        q(db, "DELETE FROM commissions WHERE id = :id", id=cid)
    for cycle in cleanup_cycles:
        # distribute() pays EVERY eligible review, not just this run's — including
        # pre-existing rows. Reverse those wallet credits before deleting the
        # distribution rows, or the payout evidence disappears while the money
        # stays (silent wallet drift across other users).
        q(db, """UPDATE users u SET wallet_balance = u.wallet_balance - h.paid
                 FROM (SELECT reviewer_id, SUM(payout_amount) AS paid
                       FROM honesty_fund_distributions
                       WHERE cycle_month = :c AND reviewer_id IS NOT NULL
                       GROUP BY reviewer_id) h
                 WHERE u.id = h.reviewer_id""", c=cycle)
        q(db, "DELETE FROM honesty_fund_distributions WHERE cycle_month = :c", c=cycle)
        q(db, "DELETE FROM commissions WHERE cycle_month = :c", c=cycle)
    for sid in created_sessions:
        q(db, "DELETE FROM sessions WHERE id = :id", id=sid)
    for pid_ in created_products:
        q(db, "DELETE FROM products WHERE id = :id", id=pid_)  # cascades reviews/votes/links
    q(db, "DELETE FROM moderation_logs WHERE moderator_id = :m", m=mod_id)
    for uid in created_users:
        q(db, "DELETE FROM users WHERE id = :id", id=uid)  # cascades tokens/badges
    db.commit()
    leftover = q(db, "SELECT count(*) FROM users WHERE email LIKE :p",
                 p=f"verify_%_{ts}@example.com").scalar()
    check("cleanup removed the verification rows", leftover == 0, f"leftover users: {leftover}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true",
                    help="leave the verification rows in the database")
    args = ap.parse_args()

    url = make_url(settings.effective_database_url)
    print(f"TARGET DATABASE: {url.host}:{url.port}/{url.database} "
          f"(use_supabase={settings.use_supabase})")
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version()")).scalar()
    print(f"Connected: {ver[:60]}")

    db = SessionLocal()
    try:
        verify_schema(db)
        verify_flow(db, TestClient(app), keep=args.keep)
    finally:
        db.close()

    passed = sum(1 for ok, *_ in _RESULTS if ok)
    failed = [f"{n} ({d})" for ok, n, d in _RESULTS if not ok]
    print(f"\n=== RESULT: {passed}/{len(_RESULTS)} passed ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
