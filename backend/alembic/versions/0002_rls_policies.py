"""row-level security policies (defense-in-depth)

RLS is the second enforcement layer behind API-level RBAC (Architecture §7). The
backend uses the Supabase service-role key for privileged jobs, which BYPASSES
RLS; these policies constrain the `anon` / `authenticated` roles the frontend and
user-scoped reads run as.

Parity: an idempotent `auth.uid()` shim is created only when absent, so this same
migration runs on local Postgres (no Supabase auth) and on Supabase (where the
built-in `auth.uid()` already exists and is left untouched).

Note: on local Postgres the table owner bypasses RLS, so enforcement is exercised
against Supabase's anon/authenticated roles; locally we assert the policies exist.

Revision ID: 0002_rls_policies
Revises: 34e54f57eca0
"""
from __future__ import annotations

from alembic import op

revision = "0002_rls_policies"
down_revision = "34e54f57eca0"
branch_labels = None
depends_on = None

# (table, owner_column): public SELECT, owner-only INSERT/UPDATE/DELETE.
OWNER_TABLES = {
    "reviews": "author_id",
    "questions": "asker_id",
    "answers": "responder_id",
    "seller_reviews": "reviewer_id",
    "price_history": "submitted_by",
    "earn_eligible_votes": "voter_id",
}

# Public SELECT, authenticated INSERT tagged to the caller; no user UPDATE/DELETE.
SUBMIT_TABLES = {
    "products": "submitted_by",
}

# Public SELECT only (reference data / public display); writes via service role.
PUBLIC_READ_TABLES = ["badges", "user_badges", "product_platforms"]

# RLS on, NO permissive policy -> default-deny for anon/authenticated; only the
# service role (privileged jobs) may touch these.
ADMIN_ONLY_TABLES = [
    "sessions", "commissions", "honesty_fund_distributions", "moderation_logs",
]

AUTH_UID_SHIM = """
CREATE SCHEMA IF NOT EXISTS auth;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'uid'
    ) THEN
        CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $fn$
            SELECT NULLIF(
                current_setting('request.jwt.claims', true)::json->>'sub', ''
            )::uuid;
        $fn$;
    END IF;
END $$;
"""


def _enable(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.execute(AUTH_UID_SHIM)

    # users: publicly readable profiles; a user may update only their own row.
    _enable("users")
    op.execute("CREATE POLICY users_select_public ON users FOR SELECT USING (true);")
    op.execute("CREATE POLICY users_update_self ON users FOR UPDATE "
               "USING (id = auth.uid()) WITH CHECK (id = auth.uid());")

    for table, owner in OWNER_TABLES.items():
        _enable(table)
        op.execute(f"CREATE POLICY {table}_select_public ON {table} FOR SELECT USING (true);")
        op.execute(f"CREATE POLICY {table}_insert_own ON {table} FOR INSERT "
                   f"WITH CHECK ({owner} = auth.uid());")
        op.execute(f"CREATE POLICY {table}_update_own ON {table} FOR UPDATE "
                   f"USING ({owner} = auth.uid()) WITH CHECK ({owner} = auth.uid());")
        op.execute(f"CREATE POLICY {table}_delete_own ON {table} FOR DELETE "
                   f"USING ({owner} = auth.uid());")

    for table, owner in SUBMIT_TABLES.items():
        _enable(table)
        op.execute(f"CREATE POLICY {table}_select_public ON {table} FOR SELECT USING (true);")
        op.execute(f"CREATE POLICY {table}_insert_own ON {table} FOR INSERT "
                   f"WITH CHECK ({owner} = auth.uid());")

    for table in PUBLIC_READ_TABLES:
        _enable(table)
        op.execute(f"CREATE POLICY {table}_select_public ON {table} FOR SELECT USING (true);")

    for table in ADMIN_ONLY_TABLES:
        _enable(table)
        # Intentionally no policy: default-deny for non-service roles.


def downgrade() -> None:
    tables = (["users"] + list(OWNER_TABLES) + list(SUBMIT_TABLES)
              + PUBLIC_READ_TABLES + ADMIN_ONLY_TABLES)
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        # Policies drop automatically when RLS objects are removed with the table;
        # explicit drops keep re-run cleanliness.
        op.execute(f"DROP POLICY IF EXISTS {table}_select_public ON {table};")
    op.execute("DROP POLICY IF EXISTS users_update_self ON users;")
    for table, _ in OWNER_TABLES.items():
        for suffix in ("insert_own", "update_own", "delete_own"):
            op.execute(f"DROP POLICY IF EXISTS {table}_{suffix} ON {table};")
    for table in SUBMIT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table};")
