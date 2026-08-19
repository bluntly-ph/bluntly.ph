"""Flag migrations whose ROLLOUT ORDER matters, before you apply them.

On 2026-08-19 migration 0023 dropped `reviews.receipt_url` while the deployed
build still selected that column. The migration was correct; applying it ahead
of compatible code took the production API down. This script exists to make
that class of migration visible *before* it is applied.

Deliberately advisory. It prints and explains; it does not block and it has no
override to remember, because a checker that blocks legitimate work is a
checker that gets commented out. The judgement stays with the person deploying.

Usage:
    cd backend && python -m scripts.check_migration_safety           # pending only
    cd backend && python -m scripts.check_migration_safety --all     # every migration
"""

from __future__ import annotations

import argparse
import pathlib
import re

VERSIONS = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions"

# (regex, label, why the rollout order matters)
PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bop\.drop_column\b"), "DROP COLUMN",
     "Deployed code that still SELECTs this column will 500. Deploy code that "
     "no longer references it first, then drop in a later migration."),
    (re.compile(r"\bop\.drop_table\b"), "DROP TABLE",
     "Same as DROP COLUMN, with more of the app affected at once."),
    (re.compile(r"\bop\.drop_constraint\b"), "DROP CONSTRAINT",
     "Usually safe, but check nothing relies on the guarantee it provided."),
    (re.compile(r"\bop\.alter_column\b[^)]*nullable\s*=\s*False", re.S), "SET NOT NULL",
     "Fails outright if any existing row is NULL, and rejects writes from "
     "deployed code that still omits the column. Backfill first, in a "
     "separate migration, then tighten."),
    (re.compile(r"\bop\.alter_column\b[^)]*type_\s*=", re.S), "TYPE CHANGE",
     "Narrowing a type can truncate or fail mid-rewrite. Confirm the "
     "conversion is widening, or expand/contract via a new column."),
    (re.compile(r"\bop\.alter_column\b[^)]*new_column_name", re.S), "RENAME COLUMN",
     "A rename is a drop and an add to deployed code. Add the new name, "
     "dual-write, migrate reads, then drop the old one."),
    (re.compile(r"\bop\.rename_table\b"), "RENAME TABLE", "As for RENAME COLUMN."),
    (re.compile(r"\bTRUNCATE\b", re.I), "TRUNCATE",
     "Data destruction does not belong in a migration. Use a guarded script."),
    (re.compile(r"\bDELETE\s+FROM\b", re.I), "DELETE FROM",
     "Row deletion in a migration is unreviewable and irreversible. Prefer a "
     "guarded script with a dry run."),
    (re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.I), "DATA REWRITE",
     "Fine when additive and backfilling, but it locks rows on a large table. "
     "Check the row count before applying to production."),
)


def applied_revision() -> str | None:
    """The revision production/local is currently at, or None if unreachable."""
    try:
        from sqlalchemy import text

        from app.db.session import engine
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001
        return None


def scan(path: pathlib.Path) -> list[tuple[str, str]]:
    src = path.read_text(encoding="utf-8", errors="replace")
    # Ignore the downgrade() body: reversing an expand is expected to contract.
    upgrade = src.split("def downgrade")[0]
    return [(label, why) for pattern, label, why in PATTERNS if pattern.search(upgrade)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true",
                    help="Scan every migration, not just unapplied ones.")
    args = ap.parse_args()

    current = applied_revision()
    files = sorted(p for p in VERSIONS.glob("*.py") if p.name != "__init__.py")

    print(f"[migration-safety] scanning {len(files)} migration(s)")
    print(f"[migration-safety] database is at: {current or 'unknown (not reachable)'}\n")

    # "Pending" = lexically after the applied revision. The numbered filenames
    # sort in apply order, which is why this cheap check is reliable here.
    pending = files
    if not args.all and current:
        after = [p for p in files if p.stem > current]
        pending = after or []
        if not pending:
            print("Nothing pending. Use --all to scan the whole history.\n")

    flagged = 0
    for path in pending:
        findings = scan(path)
        if not findings:
            continue
        flagged += 1
        print(f"  {path.name}")
        for label, why in findings:
            print(f"    [{label}]")
            for line in _wrap(why, 68):
                print(f"      {line}")
        print()

    if flagged:
        print(f"{flagged} migration(s) need a deliberate rollout order.")
        print("Expand -> deploy -> backfill -> verify -> switch -> contract.")
        print("See docs/ENVIRONMENTS.md.")
    else:
        print("No contracting operations found in the scanned migrations.")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
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
