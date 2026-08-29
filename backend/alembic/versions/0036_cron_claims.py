"""scheduler: row-based claims and resumable sweeps

Two production-runtime facts made the first design unsafe, and neither is
visible from reading the code alone.

ADVISORY LOCKS CANNOT WORK HERE. The application connects through the Supabase
TRANSACTION pooler — a deliberate, documented choice, because the session
pooler accepts only about four concurrent clients. PgBouncer in transaction
mode assigns a backend per TRANSACTION, so a session-level advisory lock taken
in one transaction sits on a backend that is handed back at commit; the unlock
in a later transaction may reach a different backend entirely, leaving the lock
held until that connection is recycled. A dedicated SQLAlchemy connection does
not fix it, because the multiplexing happens underneath SQLAlchemy.

So the lock becomes a row. Claiming a period is an INSERT that either succeeds
or violates a unique index — mutual exclusion the pooler cannot undermine,
because it is one statement and the database arbitrates it.

SWEEPS CAN OUTGROW A SERVERLESS REQUEST. `recompute_all_trust` recomputes every
recently-active user one at a time. CI measured that at 82 minutes against
~7,000 users. No serverless request survives that, and `vercel.json` sets no
maxDuration, so the platform default applies. Truncating the sweep would be
worse than useless — it would silently stop recomputing most users while
reporting success.

So long sweeps become resumable: each invocation processes a bounded batch,
persists a cursor, and returns `continuing`. The scheduler calls again until
the traversal completes. The period is marked `ok` ONLY when the whole eligible
population has been covered, so the unique index still means "this period's
work is finished" rather than "one batch of it worked".

Production selector semantics are untouched: no LIMIT on who is eligible, no
sampling. The batching is over the SAME full population, in keyset order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036_cron_claims"
down_revision = "0035_cron_periods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Resumable traversal state.
    op.add_column("cron_runs", sa.Column("cursor", sa.String(64), nullable=True))
    op.add_column("cron_runs", sa.Column(
        "processed_total", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("cron_runs", sa.Column(
        "claimed_at", sa.DateTime(timezone=True), nullable=True))

    # The claim. A period may have at most one row that is either finished or
    # in flight; that single unique index is the whole mutual-exclusion
    # mechanism, and it holds regardless of connection pooling.
    #
    # `failed` and the `skipped_*` outcomes are deliberately outside it: a
    # failed period must be retryable, and skips are history rather than claims.
    op.drop_index("uq_cron_runs_task_period_ok", table_name="cron_runs")
    op.create_index(
        "uq_cron_runs_task_period_claim", "cron_runs", ["task", "period"],
        unique=True,
        postgresql_where=sa.text(
            "period IS NOT NULL AND status IN ('running', 'continuing', 'ok')"))


def downgrade() -> None:
    op.drop_index("uq_cron_runs_task_period_claim", table_name="cron_runs")
    op.create_index(
        "uq_cron_runs_task_period_ok", "cron_runs", ["task", "period"],
        unique=True, postgresql_where=sa.text("status = 'ok' AND period IS NOT NULL"))
    op.drop_column("cron_runs", "claimed_at")
    op.drop_column("cron_runs", "processed_total")
    op.drop_column("cron_runs", "cursor")
