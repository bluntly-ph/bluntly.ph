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
