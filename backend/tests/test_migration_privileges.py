"""No migration may hand application tables back to a public role.

`0029` revoked `anon` and `authenticated` from the public schema after a
`USING (true)` SELECT policy exposed every column of 17 tables over PostgREST —
`users.password_hash`, `users.email`, `users.payout_account` and
`reviews.receipt_key` among them.

Nothing would notice it coming back. The application does not use PostgREST, so
no test fails and no page breaks; the tables simply become readable again. The
DB-backed assertions in `test_postgrest_surface.py` would catch it, but they
skip without a Postgres — which is the condition this repository is usually in.
These run anywhere, by reading the migrations themselves.

`ALTER DEFAULT PRIVILEGES` is the one that matters most: it grants nothing
today and everything tomorrow, to tables nobody has written yet.
"""

from __future__ import annotations

import pathlib
import re

import pytest

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"

GRANT_TO_PUBLIC_ROLE = re.compile(
    r"\bGRANT\b[\s\S]{0,200}?\bTO\b[\s\S]{0,80}?\b(anon|authenticated|PUBLIC)\b",
    re.I)
DEFAULT_PRIVILEGES_GRANT = re.compile(
    r"ALTER\s+DEFAULT\s+PRIVILEGES[\s\S]{0,200}?\bGRANT\b", re.I)


def migrations() -> list[pathlib.Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if p.name != "__init__.py")


def upgrade_body(path: pathlib.Path) -> str:
    """Only `upgrade()`. A downgrade restoring a grant is the point of a
    downgrade, and 0029's is deliberately empty for exactly this reason."""
    return path.read_text(encoding="utf-8", errors="replace").split("def downgrade")[0]


@pytest.mark.parametrize("path", migrations(), ids=lambda p: p.stem)
def test_no_migration_grants_to_a_public_role(path):
    match = GRANT_TO_PUBLIC_ROLE.search(upgrade_body(path))
    assert not match, (
        f"{path.name} grants to a public role: {match.group(0)[:70]!r}. That "
        f"reopens direct PostgREST access to application tables — see 0029.")


@pytest.mark.parametrize("path", migrations(), ids=lambda p: p.stem)
def test_no_migration_grants_default_privileges(path):
    match = DEFAULT_PRIVILEGES_GRANT.search(upgrade_body(path))
    assert not match, (
        f"{path.name} grants default privileges: {match.group(0)[:70]!r}. That "
        f"makes every table created afterwards reachable, including ones that "
        f"do not exist yet.")


def test_the_revocation_migration_is_still_present():
    """If 0029 is ever dropped from the chain, the schema silently reopens."""
    names = [p.stem for p in migrations()]
    assert any("revoke_postgrest" in n for n in names), (
        "the migration that revokes anon/authenticated is gone from the chain")


class TestTheDetectorActuallyDetects:
    """A guard nobody has seen fire is a guard nobody should trust."""

    @pytest.mark.parametrize("sql", [
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon",
        "GRANT ALL ON products TO authenticated",
        "grant select on users to PUBLIC",
        "GRANT SELECT\n  ON ALL TABLES IN SCHEMA public\n  TO anon, authenticated",
    ])
    def test_it_catches_a_grant(self, sql):
        assert GRANT_TO_PUBLIC_ROLE.search(sql)

    @pytest.mark.parametrize("sql", [
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon",
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT ALL ON SEQUENCES TO authenticated",
    ])
    def test_it_catches_default_privileges(self, sql):
        assert DEFAULT_PRIVILEGES_GRANT.search(sql)

    @pytest.mark.parametrize("sql", [
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated",
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM anon",
        "GRANT SELECT ON products TO service_role",
    ])
    def test_it_leaves_revocations_and_service_role_alone(self, sql):
        assert not GRANT_TO_PUBLIC_ROLE.search(sql)
        assert not DEFAULT_PRIVILEGES_GRANT.search(sql)
