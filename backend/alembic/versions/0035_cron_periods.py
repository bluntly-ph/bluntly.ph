"""scheduler: execution periods, and the timestamp columns 0034 missed

Two corrections to the scheduled-maintenance tables.

First, 0034 created both tables without `updated_at`. The models inherit the
`Timestamps` mixin, which declares created_at AND updated_at, so every query
against them failed with UndefinedColumn. Same class of mismatch as the UUID
that took the admin Overview down: the model said one thing and the schema
another, and only a real database could tell us.

Second, and more important, the scheduler needed a notion of WHICH RUN a given
execution belongs to.

GitHub Actions does not guarantee delivery. A scheduled workflow can be late,
can be dropped under load, can be retried, and can overlap. The first cut keyed
the two monthly jobs off "is today the 1st in Manila", which means a missed
invocation silently postpones the Honesty Fund distribution BY A MONTH — the
scheduler quietly not doing the one thing it exists to do.

So each execution now carries a logical period: `2026-08-29` for a daily job,
`2026-08` for a monthly one, always derived in Asia/Manila rather than from
whatever timezone the runner happens to be in. Eligibility becomes "this
period's threshold has passed and this period has no successful run yet", which
catches up instead of skipping: a run that arrives on the 2nd still completes
August, and the next one that day finds August already done.

The partial unique index is what makes that safe under concurrency — two
runners racing the same period cannot both record success, whatever the
application logic believes. Failures are deliberately NOT covered by it: a
period that failed must be allowed to retry.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_cron_periods"
down_revision = "0034_scheduled_maintenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- the columns 0034 should have created -----------------------------
    for table in ("cron_runs", "cron_credentials"):
        op.add_column(table, sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()")))

    # --- logical execution period -----------------------------------------
    op.add_column("cron_runs", sa.Column("period", sa.String(16), nullable=True))
    op.add_column("cron_runs", sa.Column(
        "scheduled_for", sa.DateTime(timezone=True), nullable=True))

    # At most one SUCCESSFUL run per (task, period). Partial, so a failed or
    # skipped period can be retried as many times as the scheduler offers.
    op.create_index(
        "uq_cron_runs_task_period_ok", "cron_runs", ["task", "period"],
        unique=True, postgresql_where=sa.text("status = 'ok' AND period IS NOT NULL"))
    op.create_index("ix_cron_runs_period", "cron_runs", ["period"])


def downgrade() -> None:
    op.drop_index("ix_cron_runs_period", table_name="cron_runs")
    op.drop_index("uq_cron_runs_task_period_ok", table_name="cron_runs")
    op.drop_column("cron_runs", "scheduled_for")
    op.drop_column("cron_runs", "period")
    for table in ("cron_credentials", "cron_runs"):
        op.drop_column(table, "updated_at")
