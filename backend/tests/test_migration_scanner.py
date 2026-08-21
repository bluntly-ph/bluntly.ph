"""The migration safety scanner must read code, not prose.

`0029_revoke_postgrest_access` was reported as
`[TRUNCATE] Data destruction does not belong in a migration`. It destroys
nothing: it revokes grants, and the word appears in a comment explaining that
TRUNCATE is the one privilege `ALL` does not imply. TRUNCATE is also a
privilege name, so it appears legitimately in any GRANT or REVOKE list.

This matters more now that the report is a CI step. A scanner that reads its
own explanatory comments as evidence produces findings nobody can act on, and
a report that cries wolf is one people stop reading — which is worse than not
having it, because the real finding arrives in the same list.
"""

from __future__ import annotations

from scripts.check_migration_safety import PATTERNS, _strip_prose


def _labels(src: str) -> list[str]:
    stripped = _strip_prose(src)
    return [label for pattern, label, _ in PATTERNS if pattern.search(stripped)]


def test_a_real_truncate_is_still_reported():
    assert "TRUNCATE" in _labels('def upgrade():\n    op.execute("TRUNCATE TABLE reviews")\n')


def test_a_real_delete_is_still_reported():
    assert "DELETE FROM" in _labels(
        'def upgrade():\n    op.execute("DELETE FROM users WHERE spam")\n')


def test_truncate_in_a_comment_is_not_a_finding():
    src = ('def upgrade():\n'
           '    # TRUNCATE is the exception to ALL, hence the explicit grant.\n'
           '    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon")\n')
    assert _labels(src) == []


def test_truncate_in_a_docstring_is_not_a_finding():
    src = ('def upgrade():\n'
           '    """Revokes grants. TRUNCATE is a privilege, not an action here."""\n'
           '    op.execute("GRANT SELECT ON x TO service_role")\n')
    assert _labels(src) == []


def test_the_real_0029_migration_is_clean():
    """The migration that prompted this, checked as it actually ships."""
    import pathlib

    path = (pathlib.Path(__file__).resolve().parents[1]
            / "alembic" / "versions" / "0029_revoke_postgrest_access.py")
    if not path.is_file():          # renamed or squashed later; not this test's business
        return
    from scripts.check_migration_safety import scan

    assert "TRUNCATE" not in [label for label, _ in scan(path)]


def test_the_whole_chain_renders_offline():
    """`alembic upgrade head --sql` must work without a database.

    Offline rendering is how a migration gets reviewed before it is applied,
    and how a fresh database gets built where no direct connection is available
    — which is exactly the position the isolated test project was in: empty,
    with its password held only in a dashboard.

    `0027` broke it by reading `result.rowcount` from `op.execute`, which
    returns None in offline mode, so the chain died four migrations short of
    head and the failure looked like a broken migration rather than a mode it
    had never supported.
    """
    import os
    import pathlib
    import subprocess
    import sys

    backend = pathlib.Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "BLUNTLY_TEST_ENV": "1",
        "APP_ENV": "test",
        # Offline mode never connects; this only has to satisfy the guard.
        "DATABASE_URL": "postgresql+psycopg://ci:ci@localhost:5432/ci",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend, env=env, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, f"offline render failed:\n{proc.stderr[-2000:]}"
    # It must reach head, not merely exit cleanly partway.
    assert "0030_tier_share_bounds" in proc.stdout, "chain did not reach head"
    assert "CREATE TABLE alembic_version" in proc.stdout


def test_every_revision_id_fits_the_version_column():
    """Alembic's `alembic_version.version_num` is VARCHAR(32).

    A longer id parses, migrates, and then fails on the bookkeeping UPDATE:

        StringDataRightTruncation: value too long for type character varying(32)
        UPDATE alembic_version SET version_num='0027_normalize_product_categories'

    That is 33 characters. The chain built 28 tables on a fresh database and
    then died four migrations short of head, which is invisible anywhere that
    already migrated past the offending revision — the value is never written
    again once you are beyond it. It only surfaces when someone builds a
    database from nothing, which is exactly what the isolated test project is
    for and exactly what had never run.

    Cheap to check, and the failure it prevents costs a CI cycle to diagnose.
    """
    import pathlib
    import re

    versions = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    too_long = {}
    for path in versions.glob("*.py"):
        match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']',
                          path.read_text(encoding="utf-8"), re.M)
        if match and len(match.group(1)) > 32:
            too_long[path.name] = (match.group(1), len(match.group(1)))

    assert not too_long, (
        "revision id longer than alembic_version.version_num VARCHAR(32): "
        + "; ".join(f"{f}: {rid!r} is {n} chars" for f, (rid, n) in too_long.items()))
