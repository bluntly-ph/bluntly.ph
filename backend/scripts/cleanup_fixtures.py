"""Remove test-suite fixtures from a database. Dry-run by default.

Why this exists: the suite wrote to production for months, so the live database
holds ~2,358 synthetic accounts and ~731 synthetic reviews against 6 real
published reviews. `reset_and_seed` is not the tool for this - it TRUNCATEs
everything including real content.

**Classification is deterministic, never heuristic.** The only accounts treated
as synthetic are `@example.com`, because `tests/conftest.register_and_token`
generates exactly `t_{uuid}@example.com` and nothing else in the system does.
Everything else is preserved, including:

  * @gmail.com          - real people who signed up
  * @showcase.bluntly.ph - the curated demo accounts that author all 6 public
                           reviews (seed_showcase.py); content, not fixtures
  * @bluntly.ph          - the platform admin
  * @example.ph          - one QA persona. NOT the test-suite pattern, so it is
                           UNCERTAIN and therefore kept. Age and inactivity are
                           never used as signals.

A product needs TWO independent signals before it is removed: it was submitted
by a synthetic account AND no non-synthetic author has reviewed it. A product
is not synthetic merely because its synthetic reviews went away.

Order matters more than it looks. `reviews.author_id` is ON DELETE **SET
NULL**, so deleting users first would silently orphan 731 reviews rather than
remove them. Reviews are therefore deleted explicitly, before users.

Usage:
    python -m scripts.cleanup_fixtures                     # dry run
    python -m scripts.cleanup_fixtures --export DIR        # dry run + rollback export
    python -m scripts.cleanup_fixtures --export DIR --apply --allow-production
"""

from __future__ import annotations

import argparse
import json
import pathlib
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

from app.core.env_guard import guard_cli
from app.db.session import SessionLocal

# The one deterministic marker. Deliberately not a list of "test-looking"
# patterns: a heuristic that grows is a heuristic that eventually eats
# something real.
SYNTHETIC_EMAIL = "%@example.com"

USERS = "SELECT id FROM users WHERE email LIKE :pat"
REVIEWS = f"SELECT r.id FROM reviews r JOIN users u ON u.id = r.author_id WHERE u.email LIKE :pat"
PRODUCTS = """
    SELECT p.id FROM products p
     WHERE p.submitted_by IN (SELECT id FROM users WHERE email LIKE :pat)
       AND NOT EXISTS (
             SELECT 1 FROM reviews r JOIN users u2 ON u2.id = r.author_id
              WHERE r.product_id = p.id AND u2.email NOT LIKE :pat)
"""

# Tables exported before deletion, in dependency order. Everything else reaches
# them through ON DELETE CASCADE from users/reviews/products, which the FK graph
# confirms; the explicit ones here are the SET NULL edges plus the polymorphic
# moderation_logs, which has no FK at all.
EXPORT_PLAN: tuple[tuple[str, str], ...] = (
    ("review_comment_votes", "SELECT * FROM review_comment_votes WHERE voter_id IN (%(u)s)"),
    ("review_votes", "SELECT * FROM review_votes WHERE voter_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("earn_eligible_votes", "SELECT * FROM earn_eligible_votes WHERE voter_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("request_upvotes", "SELECT * FROM request_upvotes WHERE user_id IN (%(u)s)"),
    ("review_comments", "SELECT * FROM review_comments WHERE author_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("review_versions", "SELECT * FROM review_versions WHERE review_id IN (%(r)s)"),
    ("referral_links", "SELECT * FROM referral_links WHERE review_id IN (%(r)s)"),
    ("review_contracts", "SELECT * FROM review_contracts WHERE review_id IN (%(r)s)"),
    ("answers", "SELECT * FROM answers WHERE responder_id IN (%(u)s)"),
    ("questions", "SELECT * FROM questions WHERE asker_id IN (%(u)s)"),
    ("price_history", "SELECT * FROM price_history WHERE submitted_by IN (%(u)s)"),
    ("review_requests", "SELECT * FROM review_requests WHERE requester_id IN (%(u)s)"),
    ("token_transactions", "SELECT * FROM token_transactions WHERE user_id IN (%(u)s)"),
    ("user_badges", "SELECT * FROM user_badges WHERE user_id IN (%(u)s)"),
    ("sessions", "SELECT * FROM sessions WHERE user_id IN (%(u)s)"),
    ("moderation_logs", "SELECT * FROM moderation_logs WHERE moderator_id IN (%(u)s) OR reporter_id IN (%(u)s) OR target_ref IN (%(r)s)"),
    ("commissions", "SELECT * FROM commissions WHERE review_id IN (%(r)s)"),
    ("honesty_fund_distributions", "SELECT * FROM honesty_fund_distributions WHERE review_id IN (%(r)s)"),
    ("affiliate_postbacks", "SELECT * FROM affiliate_postbacks WHERE review_id IN (%(r)s)"),
    ("reviews", "SELECT * FROM reviews WHERE id IN (%(r)s)"),
    ("users", "SELECT * FROM users WHERE id IN (%(u)s)"),
    ("products", "SELECT * FROM products WHERE id IN (%(p)s)"),
)

# Deletion order: children first. reviews before users (SET NULL), products last.
DELETE_PLAN: tuple[tuple[str, str], ...] = (
    ("moderation_logs", "DELETE FROM moderation_logs WHERE moderator_id IN (%(u)s) OR reporter_id IN (%(u)s) OR target_ref IN (%(r)s)"),
    ("review_comment_votes", "DELETE FROM review_comment_votes WHERE voter_id IN (%(u)s)"),
    ("review_votes", "DELETE FROM review_votes WHERE voter_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("earn_eligible_votes", "DELETE FROM earn_eligible_votes WHERE voter_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("request_upvotes", "DELETE FROM request_upvotes WHERE user_id IN (%(u)s)"),
    ("review_comments", "DELETE FROM review_comments WHERE author_id IN (%(u)s) OR review_id IN (%(r)s)"),
    ("review_versions", "DELETE FROM review_versions WHERE review_id IN (%(r)s)"),
    ("referral_links", "DELETE FROM referral_links WHERE review_id IN (%(r)s)"),
    ("review_contracts", "DELETE FROM review_contracts WHERE review_id IN (%(r)s)"),
    ("answers", "DELETE FROM answers WHERE responder_id IN (%(u)s)"),
    ("questions", "DELETE FROM questions WHERE asker_id IN (%(u)s)"),
    ("price_history", "DELETE FROM price_history WHERE submitted_by IN (%(u)s)"),
    ("review_requests", "DELETE FROM review_requests WHERE requester_id IN (%(u)s)"),
    ("token_transactions", "DELETE FROM token_transactions WHERE user_id IN (%(u)s)"),
    ("user_badges", "DELETE FROM user_badges WHERE user_id IN (%(u)s)"),
    ("sessions", "DELETE FROM sessions WHERE user_id IN (%(u)s)"),
    # These three carry ON DELETE SET NULL on review_id, and `commissions` has a
    # CHECK requiring target_type='review' to keep a non-null review_id - so
    # deleting a review NULLs the column and violates the constraint. Found by
    # the first run, which rolled back cleanly rather than half-applying.
    ("commissions", "DELETE FROM commissions WHERE review_id IN (%(r)s)"),
    ("honesty_fund_distributions", "DELETE FROM honesty_fund_distributions WHERE review_id IN (%(r)s)"),
    ("affiliate_postbacks", "DELETE FROM affiliate_postbacks WHERE review_id IN (%(r)s)"),
    ("reviews", "DELETE FROM reviews WHERE id IN (%(r)s)"),
    # Products BEFORE users, not after. The product predicate reads
    # `submitted_by IN (synthetic users)`, so running it after the users are
    # gone matched nothing: the first execution reported 0 products deleted and
    # left 687 behind. Nothing was wrongly removed - the bug fails safe - but it
    # silently did half the job, which is the worse kind of bug to leave in a
    # cleanup tool.
    ("products", "DELETE FROM products WHERE id IN (%(p)s)"),
    ("users", "DELETE FROM users WHERE id IN (%(u)s)"),
)


def _sub(sql: str) -> str:
    return sql % {"u": USERS, "r": REVIEWS, "p": PRODUCTS}


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value) if value is not None and not isinstance(value, (int, float, bool, str, list, dict)) else value


def preserved_summary(db) -> dict:
    q = lambda s: db.execute(text(s), {"pat": SYNTHETIC_EMAIL}).scalar()
    return {
        "users_preserved": q("SELECT count(*) FROM users WHERE email NOT LIKE :pat"),
        "reviews_preserved": q(
            "SELECT count(*) FROM reviews r JOIN users u ON u.id=r.author_id "
            "WHERE u.email NOT LIKE :pat"),
        "public_reviews": q(
            "SELECT count(*) FROM reviews WHERE published_at IS NOT NULL AND is_removed=false"),
        "products_preserved": q(
            "SELECT count(*) FROM products p WHERE p.id NOT IN (" + PRODUCTS + ")"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Actually delete. Default is a dry run.")
    ap.add_argument("--export", metavar="DIR", help="Write the rollback export to DIR.")
    ap.add_argument("--allow-production", action="store_true",
                    help="Required to run against production. The guard prints the target first.")
    args = ap.parse_args()

    guard_cli("cleanup_fixtures", production_is_legitimate=True)

    with SessionLocal() as db:
        p = {"pat": SYNTHETIC_EMAIL}
        before = preserved_summary(db)
        counts: dict[str, int] = {}
        for name, sql in DELETE_PLAN:
            counting = _sub(sql).replace("DELETE FROM", "SELECT count(*) FROM", 1)
            counts[name] = db.execute(text(counting), p).scalar() or 0

        print("\n--- classification (deterministic: @example.com only) ---")
        print(f"  synthetic users              : {db.execute(text(USERS.replace('SELECT id', 'SELECT count(*)')), p).scalar()}")
        print(f"  synthetic reviews            : {db.execute(text(REVIEWS.replace('SELECT r.id', 'SELECT count(*)')), p).scalar()}")
        print(f"  synthetic products           : {db.execute(text('SELECT count(*) FROM (' + PRODUCTS + ') x'), p).scalar()}")
        print("\n--- rows that would be deleted, per table ---")
        for name, n in counts.items():
            print(f"  {name:22s} {n}")
        print("\n--- preserved ---")
        for k, v in before.items():
            print(f"  {k:22s} {v}")

        if args.export:
            out = pathlib.Path(args.export)
            out.mkdir(parents=True, exist_ok=True)
            manifest = {}
            for name, sql in EXPORT_PLAN:
                try:
                    rows = db.execute(text(_sub(sql)), p).mappings().all()
                except Exception as exc:  # noqa: BLE001
                    print(f"  [skip] {name}: {type(exc).__name__}")
                    continue
                data = [{k: _json_safe(v) for k, v in r.items()} for r in rows]
                (out / f"{name}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
                manifest[name] = len(data)
            (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(f"\n  rollback export written: {sum(manifest.values())} rows across {len(manifest)} tables")

        if not args.apply:
            print("\nDRY RUN. Re-run with --export DIR --apply --allow-production to execute.")
            return 0

        if not args.export:
            print("\nRefusing to delete without --export: build the rollback first.")
            return 1

        print("\n--- deleting ---")
        for name, sql in DELETE_PLAN:
            n = db.execute(text(_sub(sql)), p).rowcount
            print(f"  {name:22s} {n}")
        db.commit()

        after = preserved_summary(db)
        print("\n--- reconciliation ---")
        for k in before:
            flag = "" if before[k] == after[k] else "   <-- CHANGED"
            print(f"  {k:22s} before={before[k]} after={after[k]}{flag}")
        orphans = db.execute(text(
            "SELECT count(*) FROM reviews r LEFT JOIN users u ON u.id=r.author_id "
            "WHERE r.author_id IS NOT NULL AND u.id IS NULL")).scalar()
        print(f"  orphaned reviews       : {orphans} (must be 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
