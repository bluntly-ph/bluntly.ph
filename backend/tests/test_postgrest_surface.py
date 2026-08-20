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
def test_anon_has_no_reach_into_the_schema_at_all():
    """Belt and braces: without USAGE, the grants above cannot be exercised."""
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        usage = db.execute(text(
            "SELECT has_schema_privilege('anon', 'public', 'USAGE')")).scalar()
        assert usage is False, "anon still has USAGE on schema public"


@requires_db
def test_a_new_table_does_not_reopen_the_hole():
    """Supabase's default privileges re-grant every new table to anon.

    That is the mechanism that would have quietly undone this the next time a
    migration added a table carrying something private.
    """
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        defaults = db.execute(text("""
            SELECT count(*) FROM pg_default_acl d
            JOIN pg_namespace n ON n.oid = d.defaclnamespace
            WHERE n.nspname = 'public'
              AND array_to_string(d.defaclacl, ',') LIKE '%anon=%'
        """)).scalar()
        assert defaults == 0, (
            "a default-privileges rule still grants new objects to anon")
