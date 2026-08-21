"""The database must not be readable around the API.

Found 2026-08-20 against production: an anonymous caller holding the
publishable key - public by design - could read table rows straight over
PostgREST, past the API and every serializer in it. `users.password_hash`,
`users.email`, `users.payout_account`, `reviews.receipt_key` and
`reviews.affiliate_link` were all returned in full.

The policies were not missing; they were `USING (true)` under names like
`users_select_public`. RLS is row-level, so "this entity is public" granted
every column - including the ones the API is careful never to emit. The API's
own responses were clean throughout, which is precisely why nothing caught it:
every test pointed at the API, and the exposure was beside the API.

0029 revokes the grants. These tests keep the surface shut.
"""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import text

from tests.conftest import requires_db

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Columns that must never leave the database except through a serializer that
# chose them on purpose.
SENSITIVE = {
    "users": ("password_hash", "email", "payout_account"),
    "reviews": ("receipt_key", "affiliate_link"),
}


def test_nothing_uses_the_publishable_client():
    """The REST surface stays unused, so keeping it closed stays free.

    `get_publishable_client()` is defined and never called. If that changes,
    somebody is about to depend on PostgREST and 0029 will break them - which
    is a conversation worth having deliberately rather than at runtime.
    """
    callers = [
        p for p in APP.rglob("*.py")
        if p.name != "supabase_client.py"
        and "get_publishable_client(" in p.read_text(encoding="utf-8")
    ]
    assert not callers, (
        f"{[str(p) for p in callers]} call get_publishable_client(). PostgREST "
        "access is revoked by 0029; grant it deliberately and per column.")


@requires_db
@pytest.mark.parametrize("table,columns", sorted(SENSITIVE.items()))
def test_anon_cannot_read_sensitive_tables(db, table, columns):
    for column in columns:
        granted = db.execute(text(
            "SELECT has_column_privilege('anon', :t, :c, 'SELECT')"),
            {"t": table, "c": column}).scalar()
        assert granted is False, (
            f"anon can SELECT {table}.{column} over PostgREST, around the API")


@requires_db
def test_no_table_in_the_schema_is_readable_by_anon():
    """The decisive control, checked across every table rather than a sample.

    Schema USAGE is deliberately not asserted here. PostgreSQL grants USAGE on
    `public` to the PUBLIC pseudo-role, every role inherits from PUBLIC, and
    revoking from `anon` by name does not take away what PUBLIC gives. Chasing
    it would mean revoking from PUBLIC, which reaches roles this migration has
    no business touching.

    It does not matter: USAGE only permits name resolution. Without a table
    privilege there is nothing to resolve to, and that is what this asserts.
    """
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        readable = db.execute(text("""
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND has_table_privilege('anon', c.oid, 'SELECT')
            ORDER BY c.relname
        """)).scalars().all()
        assert not readable, (
            f"{len(readable)} table(s) still readable by anon over PostgREST: "
            f"{readable}")


@requires_db
def test_a_table_created_by_a_migration_does_not_reopen_the_hole():
    """Supabase's default privileges re-grant new objects to anon.

    That is the mechanism that would quietly undo `0029` the next time a
    migration adds a table carrying something private — so what matters is the
    defaults belonging to **the role migrations actually run as**, which is
    `postgres`. `0029` revokes those, and this asserts it stayed revoked.

    This test used to require that NO role in `public` had such a rule, which
    is not achievable on Supabase and failed against production as surely as
    against a fresh database. `supabase_admin` also carries one, only that role
    or a superuser may change it, and Supabase does not grant the project's
    `postgres` role that power — `0029` attempts it and tolerates the refusal.

    The narrower assertion is the true one. A table created by our migrations
    is not exposed; a table created by Supabase's own tooling under
    `supabase_admin` would be. That residual risk is real, documented, and
    covered by the two `check_invariants` checks that fail the moment any table
    becomes readable by `anon` or `authenticated` — detection rather than
    prevention, which is the honest description of what is possible here.
    """
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        leaky = db.execute(text("""
            SELECT pg_get_userbyid(d.defaclrole) AS owner_role,
                   d.defaclobjtype AS obj_type
            FROM pg_default_acl d
            JOIN pg_namespace n ON n.oid = d.defaclnamespace
            WHERE n.nspname = 'public'
              AND pg_get_userbyid(d.defaclrole) = 'postgres'
              AND array_to_string(d.defaclacl, ',') LIKE '%anon=%'
        """)).all()
        assert not leaky, (
            "postgres' default privileges grant new objects to anon, so the "
            f"next migration that adds a table reopens the hole: {leaky}")
