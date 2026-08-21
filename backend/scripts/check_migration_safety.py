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
    # Raw SQL first. A destructive migration is at least as likely to be
    # written as op.execute("DROP ...") as with the Alembic helper, and an
    # earlier version of this checker matched only the helpers — so the very
    # migration that dropped seller_reviews sailed through it unflagged.
    (re.compile(r"DROP\s+TABLE", re.I), "DROP TABLE (raw SQL)",
     "Deployed code selecting from this table will 500. Confirm nothing "
     "references it, and deploy that removal before applying."),
    (re.compile(r"DROP\s+COLUMN", re.I), "DROP COLUMN (raw SQL)",
     "Same as the Alembic helper: deploy code that no longer references the "
     "column first, then drop it in a later migration."),
    (re.compile(r"ALTER\s+TYPE\s+\S+\s+ADD\s+VALUE", re.I), "ENUM ADD VALUE",
     "Additive and safe, but on PostgreSQL it cannot run inside a transaction "
     "alongside other DDL — keep it in its own migration."),
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
    # Privilege regressions. 0029 revoked anon/authenticated from the public
    # schema after a `USING (true)` policy exposed every column of 17 tables
    # over PostgREST, `users.password_hash` among them. Nothing else would
    # notice a migration handing it back.
    (re.compile(r"\bGRANT\b[\s\S]{0,200}?\bTO\b[\s\S]{0,80}?"
                r"\b(anon|authenticated|PUBLIC)\b", re.I),
     "GRANT TO A PUBLIC ROLE",
     "This reopens direct PostgREST access to application tables. If it is "
     "genuinely wanted, grant it per column, and record why it is safe for "
     "every column of that table."),
    (re.compile(r"ALTER\s+DEFAULT\s+PRIVILEGES[\s\S]{0,200}?\bGRANT\b", re.I),
     "DEFAULT PRIVILEGES GRANT",
     "This makes every table created afterwards reachable, including ones "
     "nobody has written yet. It is how the exposure comes back without "
     "anyone touching a policy."),
    (re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.I), "DATA REWRITE",
     "Fine when additive and backfilling, but it locks rows on a large table. "
     "Check the row count before applying to production."),
)


#: Seconds to wait when asking the database where it is. Short on purpose: the
#: answer only decides whether to scan every migration or the pending ones, so
#: being wrong costs a longer report while being slow costs the whole run.
REVISION_PROBE_TIMEOUT_SECONDS = 3


def applied_revision() -> str | None:
    """The revision production/local is currently at, or None if unreachable.

    Its own engine, with an explicit connect timeout, rather than the
    application's. A refused connection fails in milliseconds — which is why
    this looked fine for a long time — but a port that silently drops packets
    never fails at all, and the application engine has no timeout to stop it
    waiting. Measured here: the tool sat for over six minutes and printed
    nothing. Same fault as `tests/conftest.db_available`, same fix.
    """
    probe = None
    try:
        from sqlalchemy import create_engine, text

        from app.core.config import settings
        probe = create_engine(
            settings.effective_database_url,
            connect_args={"connect_timeout": REVISION_PROBE_TIMEOUT_SECONDS},
            pool_pre_ping=False,
        )
        with probe.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001
        return None
    finally:
        if probe is not None:
            probe.dispose()


def _strip_prose(src: str) -> str:
    """Remove comments and docstrings so prose cannot look like a statement.

    `0029_revoke_postgrest_access` was reported as `[TRUNCATE] Data destruction
    does not belong in a migration`. It destroys nothing — it revokes grants,
    and the word appears in a *comment* explaining that TRUNCATE is the one
    privilege `ALL` does not imply. `TRUNCATE` is also a privilege name, so it
    shows up legitimately in any GRANT or REVOKE list.

    A scanner that reads its own explanatory comments as evidence produces
    findings nobody can act on, and a report that cries wolf is one people stop
    reading — which is worse than not having it, because the real finding
    arrives in the same list.
    """
    # Blank out docstrings first (they can contain `#`), then line comments.
    without_docstrings = re.sub(r'("""|\'\'\')(?:.|\n)*?\1', '""', src)
    return re.sub(r"#[^\n]*", "", without_docstrings)


def scan(path: pathlib.Path) -> list[tuple[str, str]]:
    src = path.read_text(encoding="utf-8", errors="replace")
    # Ignore the downgrade() body: reversing an expand is expected to contract.
    upgrade = _strip_prose(src.split("def downgrade")[0])
    return [(label, why) for pattern, label, why in PATTERNS if pattern.search(upgrade)]


def check_chain() -> list[str]:
    """Structural problems that no per-migration scan can see.

    A fork in the chain, a second head, or a lost base are the failures that
    make `upgrade head` ambiguous or refuse outright, and they are invisible
    when reading migrations one at a time. Cheap to check, and the answer is
    only interesting when it is bad.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    problems: list[str] = []
    try:
        sd = ScriptDirectory.from_config(Config("alembic.ini"))
    except Exception as exc:  # noqa: BLE001
        return [f"could not read the migration chain: {type(exc).__name__}"]

    heads, bases = sd.get_heads(), sd.get_bases()
    revisions = list(sd.walk_revisions())
    if len(heads) != 1:
        problems.append(f"{len(heads)} heads ({', '.join(heads)}) - `upgrade head` is ambiguous")
    if len(bases) != 1:
        problems.append(f"{len(bases)} bases - the chain is not a single line")

    children: dict[str | None, list[str]] = {}
    for rev in revisions:
        downs = rev.down_revision if isinstance(rev.down_revision, tuple) else (rev.down_revision,)
        for down in downs:
            children.setdefault(down, []).append(rev.revision)
    for parent, kids in children.items():
        if len(kids) > 1:
            problems.append(f"fork after {parent}: {', '.join(kids)}")

    print(f"[chain] {len(revisions)} migrations, {len(heads)} head, {len(bases)} base"
          f" -> {'linear' if not problems else 'PROBLEMS'}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true",
                    help="Scan every migration, not just unapplied ones.")
    args = ap.parse_args()

    chain_problems = check_chain()
    for problem in chain_problems:
        print(f"  [CHAIN] {problem}")
    if chain_problems:
        print()

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
