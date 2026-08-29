"""tighten the backfilled staff reference to NOT NULL

0038 expands, backfills and installs the database default. This separate step
lets production verification prove no NULL remains before tightening instead
of hiding a data rewrite and a NOT NULL change in one operation.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0039_staff_ref_not_null"
down_revision = "0038_staff_ref_and_super_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users", "staff_ref", existing_type=sa.String(16), nullable=False)


def downgrade() -> None:
    op.alter_column(
        "users", "staff_ref", existing_type=sa.String(16), nullable=True)
