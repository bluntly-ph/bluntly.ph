"""enable RLS on alembic_version (Supabase advisor: RLS disabled in public)

Alembic's bookkeeping table lives in `public` and is therefore exposed to
PostgREST. Enable RLS so anon/authenticated get default-deny. We do NOT FORCE RLS,
so the table owner (the role Alembic connects as) still bypasses it and migrations
keep working; the service-role key also bypasses.

Revision ID: 0003_rls_alembic_version
Revises: f18b59a2227b
"""
from __future__ import annotations

from alembic import op

revision = "0003_rls_alembic_version"
down_revision = "f18b59a2227b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
