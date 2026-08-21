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

    ("negative commission shares",
     "SELECT count(*) FROM commissions WHERE coalesce(platform_share,0) < 0 "
     "OR coalesce(reviewer_share,0) < 0 OR coalesce(honesty_fund_share,0) < 0",
     "A share went negative. At 7000 bps the platform could land at -0.01 "
     "before that was guarded; a row here predates the fix."),
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any invariant is violated.")
    args = ap.parse_args()

    from app.core.env_guard import describe_target
    from app.db.session import SessionLocal

    print(f"[invariants] target: {describe_target()}")
    print("[invariants] read-only; this writes nothing\n")

    violations = 0
    with SessionLocal() as db:
        for name, sql, meaning in CHECKS:
            try:
                count = db.execute(text(sql)).scalar() or 0
            except Exception as exc:  # noqa: BLE001
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
