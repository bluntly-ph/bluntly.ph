"""Read-only integrity check: does the data still satisfy what the code assumes?

Every query here is a SELECT with a count. It writes nothing, creates nothing,
and is therefore the one check in this repository that is safe to point at
production - which is the point, because production is the only place the data
is real.

The invariants are the ones the application states in prose and then relies on:

  * `payout_service`: "wallet == inflows - SUM(payouts in scheduled/processing/paid)".
  * `referral_service`: only a verified review can be monetized, and never one
    at two stars or below.
  * `earnings`: the three commission shares sum to the gross, and none is
    negative.
  * The foreign keys, restated as orphan counts - a FK can be dropped by a
    migration and nothing else would notice.

Usage:
    cd backend && python -m scripts.check_invariants
    cd backend && python -m scripts.check_invariants --strict   # exit 1 on any violation
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

# (name, SQL returning one integer, what a non-zero result means)
CHECKS: tuple[tuple[str, str, str], ...] = (
    ("negative wallet balances",
     "SELECT count(*) FROM users WHERE wallet_balance < 0",
     "A wallet went below zero. ck_user_wallet_non_negative should make this "
     "impossible; if it fires, the constraint was dropped."),

    ("reviews with no author",
     "SELECT count(*) FROM reviews r LEFT JOIN users u ON u.id = r.author_id "
     "WHERE u.id IS NULL",
     "Orphaned reviews. The author FK is gone or was never enforced."),

    ("reviews with no product",
     "SELECT count(*) FROM reviews r LEFT JOIN products p ON p.id = r.product_id "
     "WHERE p.id IS NULL",
     "Orphaned reviews; the product they describe no longer exists."),

    ("payouts with no user",
     "SELECT count(*) FROM payouts p LEFT JOIN users u ON u.id = p.user_id "
     "WHERE u.id IS NULL",
     "Money owed to nobody."),

    ("commissions pointing at a missing review",
     "SELECT count(*) FROM commissions c LEFT JOIN reviews r ON r.id = c.review_id "
     "WHERE c.review_id IS NOT NULL AND r.id IS NULL",
     "Earnings attributed to a review that is gone."),

    ("reviews with two active referral links",
     "SELECT count(*) FROM (SELECT review_id FROM referral_links "
     "WHERE status = 'active' GROUP BY review_id HAVING count(*) > 1) x",
     "referral_service refuses a second active link; two means it was "
     "bypassed, and attribution is now ambiguous."),

    ("star ratings out of range",
     "SELECT count(*) FROM reviews WHERE star_rating NOT BETWEEN 1 AND 5",
     "Feeds avg_rating and the Wilson ranking, so one bad row skews the "
     "ordering the whole platform is built on."),

    ("reviews stranded outside the moderation queue",
     "SELECT count(*) FROM reviews WHERE is_removed = false "
     "AND published_at IS NULL "
     "AND earn_eligible_status NOT IN ('pending', 'rejected')",
     "Unpublished and not pending means invisible to readers AND absent from "
     "get_queue, which selects pending-and-unpublished. Nothing in the "
     "moderator UI can reach such a row. Two sat in production this way, one "
     "for eleven days, because the old unpublish cleared published_at without "
     "moving the status back."),

    ("monetized but unverified",
     "SELECT count(*) FROM reviews WHERE earn_eligible_status = 'monetized' "
     "AND verification_status <> 'verified'",
     "referral_service holds that only a verified review can be monetized. "
     "A row here is a state the code says is unreachable."),

    ("monetized at two stars or below",
     "SELECT count(*) FROM reviews WHERE earn_eligible_status = 'monetized' "
     "AND star_rating <= 2",
     "Low-star reviews route to the Honesty Fund and must never carry an "
     "affiliate link - that separation is the platform's whole claim."),

    ("commission splits that do not sum to the gross",
     "SELECT count(*) FROM commissions WHERE gross_amount IS NOT NULL AND "
     "coalesce(platform_share,0) + coalesce(reviewer_share,0) + "
     "coalesce(honesty_fund_share,0) <> gross_amount",
     "A centavo appeared or vanished in the 40/30/30 split."),

    ("negative commission shares on a forward entry",
     "SELECT count(*) FROM commissions WHERE reverses_commission_id IS NULL AND "
     "(coalesce(platform_share,0) < 0 OR coalesce(reviewer_share,0) < 0 "
     "OR coalesce(honesty_fund_share,0) < 0)",
     "A share went negative. At 7000 bps the platform could land at -0.01 "
     "before that was guarded; a row here predates the fix. Reversal rows are "
     "excluded on purpose - their shares are negative by design (0031), which "
     "is a paired, audited undo rather than a rounding fault."),

    ("reversals that do not oppose their original",
     "SELECT count(*) FROM commissions r JOIN commissions o "
     "ON o.id = r.reverses_commission_id "
     "WHERE r.reviewer_share <> -o.reviewer_share "
     "OR r.platform_share <> -o.platform_share "
     "OR r.honesty_fund_share <> -o.honesty_fund_share",
     "A reversal must be the exact negation of the entry it undoes. Anything "
     "else means the ledger and the wallet have quietly diverged."),

    ("reversals pointing at another reversal",
     "SELECT count(*) FROM commissions r JOIN commissions o "
     "ON o.id = r.reverses_commission_id WHERE o.reverses_commission_id IS NOT NULL",
     "A reversal of a reversal is not a correction, it is a double credit "
     "wearing a disguise."),

    ("honesty fund distributions with no reviewer",
     "SELECT count(*) FROM honesty_fund_distributions WHERE reviewer_id IS NULL",
     "A distribution records money paid to a specific reviewer. A NULL one is "
     "either fixture residue whose user was deleted, or a real payment whose "
     "recipient is now unknown - and the two look identical afterwards."),

    ("honesty fund distributions dated at the epoch",
     "SELECT count(*) FROM honesty_fund_distributions "
     "WHERE cycle_month < DATE '2020-01-01'",
     "cycle_month is the Manila month the pool was earned in. 1970-01-01 means "
     "the row was written by a fixture rather than a distribution run."),

    ("distributions whose cycle is not the first of a month",
     "SELECT count(*) FROM honesty_fund_distributions "
     "WHERE EXTRACT(DAY FROM cycle_month) <> 1",
     "previous_cycle_month() always returns the first of a month, so anything "
     "else was not written by the distributor."),

    ("commissions whose cycle is not the first of a month",
     "SELECT count(*) FROM commissions WHERE cycle_month IS NOT NULL "
     "AND EXTRACT(DAY FROM cycle_month) <> 1",
     "The Honesty Fund pools commissions by cycle_month equality, so a "
     "mid-month value can never be matched by a cycle and its share is never "
     "distributed."),

    ("tables readable by anon over PostgREST",
     "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
     "WHERE n.nspname = 'public' AND c.relkind = 'r' "
     "AND has_table_privilege('anon', c.oid, 'SELECT')",
     "0029 revoked this. A table appearing here was almost certainly created "
     "through the Supabase dashboard rather than by a migration: dashboard DDL "
     "runs as supabase_admin, whose default privileges still grant new tables "
     "to anon - and only supabase_admin can change that, which neither the "
     "postgres role nor the SQL editor can do. Migrations run as postgres and "
     "are unaffected. Revoke it, and prefer migrations for new tables."),

    ("tables readable by the authenticated role",
     "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
     "WHERE n.nspname = 'public' AND c.relkind = 'r' "
     "AND has_table_privilege('authenticated', c.oid, 'SELECT')",
     "Same cause as above. The application authenticates as postgres and never "
     "as this role, so anything reachable here is reachable around the API."),
)



#: Seconds to wait for the database. Short: this tool reports, and a report
#: that never arrives is worse than one that says it could not connect.
CONNECT_TIMEOUT_SECONDS = 5


def _probe_engine():
    from sqlalchemy import create_engine

    from app.core.config import settings
    return create_engine(
        settings.effective_database_url,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any invariant is violated.")
    args = ap.parse_args()

    from sqlalchemy.orm import Session

    from app.core.env_guard import describe_target

    print(f"[invariants] target: {describe_target()}")
    print("[invariants] read-only; this writes nothing\n")

    violations = 0
    # Its own engine with a connect timeout rather than the application's.
    # This is meant to be pointed at production from wherever the release is
    # being run, and a refused connection fails in milliseconds while a port
    # that drops packets never fails at all - the tool would sit there
    # printing nothing. Same fault found in conftest and
    # check_migration_safety, same fix.
    engine = _probe_engine()

    # Prove the connection once, before running anything. Each check catches
    # its own errors so one bad query cannot hide the rest - but that also
    # means an unreachable database is retried fifteen times, ten seconds
    # apart, and the tool appears to hang. Fail here instead, with the reason.
    try:
        with engine.connect() as probe:
            probe.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        print(f"  cannot reach the database: {type(exc).__name__}")
        print("  Nothing was checked. Confirm the target above is the one you "
              "meant, and that it is reachable from here.")
        return 2

    unrunnable: list[str] = []
    with Session(engine) as db:
        for name, sql, meaning in CHECKS:
            try:
                count = db.execute(text(sql)).scalar() or 0
            except Exception as exc:  # noqa: BLE001
                # Roll back before the next check. Postgres aborts the whole
                # transaction on any error, so without this one unrunnable
                # query turns every check after it into InternalError - which
                # is how a single missing column blinded eight of twenty here.
                db.rollback()
                unrunnable.append(name)
                print(f"  ????  {name}: could not run ({type(exc).__name__})")
                continue
            if count:
                violations += 1
                print(f"  FAIL  {name}: {count}")
                for line in _wrap(meaning, 66):
                    print(f"        {line}")
            else:
                print(f"  ok    {name}")

    print()
    if violations:
        print(f"{violations} invariant(s) violated.")
        if unrunnable:
            print(f"{len(unrunnable)} could not run at all.")
        return 1 if args.strict else 0

    # A check that could not run is not a check that passed. Reporting "all
    # invariants hold" while some never executed is the failure mode this tool
    # exists to prevent, so it is spelled out rather than rounded up.
    if unrunnable:
        print(f"{len(CHECKS) - len(unrunnable)} of {len(CHECKS)} invariants hold; "
              f"{len(unrunnable)} COULD NOT RUN:")
        for name in unrunnable:
            print(f"  - {name}")
        print()
        print("An unrunnable check is usually a schema the database has not "
              "reached yet. Verify the target's migration revision.")
        return 1 if args.strict else 0

    print(f"All {len(CHECKS)} invariants hold.")
    return 0


def _wrap(text_: str, width: int) -> list[str]:
    words, lines, cur = text_.split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
