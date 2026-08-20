"""moderation_action: add `receipt_view` (privacy/security enhancement)

Approved by the owner as an enhancement, explicitly NOT as a contractual
requirement: the PRD asks for an audit log of moderation/admin *actions*, and
everything logged today changes state. Viewing evidence is a read. It is worth
doing anyway - the architecture doc maps the audit log to ISO/IEC 27002 8.15,
which covers access logging, and a receipt is personal data under RA 10173.
"Who opened this customer's receipt, and when" is exactly what an audit log
exists to answer.

**Additive and backward compatible.** Adding a value to a PostgreSQL enum does
not rewrite rows, does not lock the table for readers, and cannot break a
deployed application: old code never emits the new value, and nothing reads
`moderation_action` expecting a closed set. So this one migration is safe to
apply in either order relative to its deploy - unlike 0023 and 0024, which
were contracting and were not.

`ALTER TYPE ... ADD VALUE` cannot run inside a transaction block alongside
other DDL, which is why this migration carries nothing else. The safety
checker flags exactly that and it is the reason this file does one thing.

There is deliberately no downgrade. Removing a value from a PostgreSQL enum
requires rebuilding the type and every column that uses it, and would fail
outright once a single row references it - a destructive operation to undo an
additive one.

Revision ID: 0025_receipt_view_audit
Revises: 0024_drop_seller_reviews
"""
from __future__ import annotations

from alembic import op

revision = "0025_receipt_view_audit"
down_revision = "0024_drop_seller_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps a re-run harmless.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE moderation_action ADD VALUE IF NOT EXISTS 'receipt_view'")


def downgrade() -> None:
    """Intentionally a no-op.

    Dropping an enum value means recreating the type and rewriting every column
    that references it, and it fails the moment one audit row uses the value.
    Leaving an unused label costs nothing; removing it risks the audit trail.
    """
