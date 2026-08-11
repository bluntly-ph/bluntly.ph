"""Hide test-suite content from the public site (BUG-010).

There is one database and it is production, so `python -m pytest` writes real
rows: `tests/conftest.py::register_and_token` creates `t_<hex>@example.com` users
named "Tester", and the review fixtures publish live reviews under them.
`scripts.verify_milestones` does the same with `mv_*` accounts. Measured
2026-08-09: 482 of 490 public reviews were test output.

This hides them rather than deleting them. `is_removed` is honoured by every
public read path — the listing endpoint, review detail, search, voting, the
affiliate redirect and trust scoring — so flipping it takes the rows off the site
while keeping them recoverable with `--revert`.

The match is deliberately narrow and is verified before anything is written:
every candidate must hold an `@example.com` address, so no real account can be
caught by a username that merely looks synthetic.

    python -m scripts.hide_test_content            # dry run, changes nothing
    python -m scripts.hide_test_content --apply
    python -m scripts.hide_test_content --revert --apply
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

from app.db.session import engine

# `t_` + 32 hex chars comes from conftest's uuid4().hex; `mv_m<n>` from the
# milestone verifier. Anchored so a real handle like "t_shirt_fan" cannot match.
TEST_ACCOUNT_PREDICATE = """
    (u.username ~ '^t_[0-9a-f]{30}$' OR u.username ~ '^mv_m[0-9]')
    AND u.email LIKE '%@example.com'
"""

COUNT_SQL = f"""
SELECT
  count(*) FILTER (WHERE NOT r.is_removed) AS visible,
  count(*) FILTER (WHERE r.is_removed)     AS hidden,
  count(*)                                  AS total
FROM reviews r JOIN users u ON u.id = r.author_id
WHERE {TEST_ACCOUNT_PREDICATE}
"""

# Guard against the predicate ever widening to catch a real account.
SAFETY_SQL = f"""
SELECT count(*) FROM users u
WHERE ({TEST_ACCOUNT_PREDICATE.replace("AND u.email LIKE '%@example.com'", "")})
  AND u.email NOT LIKE '%@example.com'
"""

PUBLIC_SQL = """
SELECT count(*) FROM reviews r
WHERE NOT r.is_removed AND r.published_at IS NOT NULL
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the change; without it this is a dry run")
    parser.add_argument("--revert", action="store_true",
                        help="unhide instead of hide")
    args = parser.parse_args()

    hiding = not args.revert
    target = "true" if hiding else "false"
    # Only touch rows that are not already in the desired state, so a re-run is a
    # no-op and `updated_at` is not churned across hundreds of rows.
    update_sql = f"""
    UPDATE reviews r SET is_removed = {target}, updated_at = now()
    FROM users u
    WHERE u.id = r.author_id
      AND r.is_removed = {'false' if hiding else 'true'}
      AND {TEST_ACCOUNT_PREDICATE}
    """

    with engine.begin() as conn:
        leaked = conn.execute(text(SAFETY_SQL)).scalar() or 0
        if leaked:
            print(f"ABORT: {leaked} matched account(s) have a non-example.com "
                  "address. The pattern may be catching real users — inspect "
                  "before running this.")
            return 1

        before = conn.execute(text(COUNT_SQL)).one()
        public_before = conn.execute(text(PUBLIC_SQL)).scalar()
        print(f"test-authored reviews : {before.total} "
              f"({before.visible} visible, {before.hidden} hidden)")
        print(f"published + visible reviews site-wide : {public_before}")

        if not args.apply:
            verb = "hide" if hiding else "restore"
            n = before.visible if hiding else before.hidden
            print(f"\nDRY RUN — would {verb} {n} review(s). Re-run with --apply.")
            return 0

        changed = conn.execute(text(update_sql)).rowcount
        after = conn.execute(text(COUNT_SQL)).one()
        public_after = conn.execute(text(PUBLIC_SQL)).scalar()

    print(f"\n{'hid' if hiding else 'restored'} {changed} review(s)")
    print(f"test-authored reviews : {after.total} "
          f"({after.visible} visible, {after.hidden} hidden)")
    print(f"published + visible reviews site-wide : {public_before} -> {public_after}")
    print("\nReversible: python -m scripts.hide_test_content "
          f"{'--revert ' if hiding else ''}--apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
