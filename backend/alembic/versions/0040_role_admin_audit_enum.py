"""audit labels for moderator grants and revocations

PostgreSQL enum additions must run outside the migration transaction and must
not share a migration with other DDL. Values cannot be safely removed after an
audit row uses them, so downgrade is intentionally a no-op.
"""

from __future__ import annotations

from alembic import op

revision = "0040_role_admin_audit_enum"
down_revision = "0039_staff_ref_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE moderation_action ADD VALUE IF NOT EXISTS 'role_grant'")
        op.execute("ALTER TYPE moderation_action ADD VALUE IF NOT EXISTS 'role_revoke'")


def downgrade() -> None:
    """Audit rows may use these labels; rebuilding the enum would destroy history."""
