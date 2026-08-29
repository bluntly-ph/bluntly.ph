"""scheduler: execution leases, fencing tokens and a traversal boundary

Three defects in 0036, two of them latent until a real database saw them.

STATUS WAS TOO NARROW. `status` was varchar(16); the value
'skipped_already_completed' is 25 characters. Every "already completed" refusal
would have failed on insert.

OWNERSHIP WAS NOT ARBITRATED BY THE DATABASE. 0036 reclaimed an in-flight row
by SELECTing it and then UPDATEing it. Two concurrent runners both read the
same row and both believed they owned it, because nothing between the read and
the write was atomic — the unique index only guards INSERTs, and a reclaim is
not an INSERT. Ownership is now a LEASE taken by a single conditional UPDATE:

    UPDATE ... SET lease_token = <new>, lease_expires_at = <now + lease>
     WHERE task = ? AND period = ?
       AND status IN ('running','continuing','failed')
       AND (lease_expires_at IS NULL OR lease_expires_at <= now)
    RETURNING ...

One statement, so the database picks the winner: the loser blocks on the row
lock, re-evaluates the predicate after the winner commits, sees a live lease
and matches zero rows. This works through PgBouncer transaction pooling for the
same reason the INSERT does — it is a single statement in a single transaction.

NOTHING WAS FENCED. A request that stalled past the takeover window, was
replaced, and then woke up would happily write its stale cursor over the new
owner's progress. Every mutation is now conditioned on `lease_token = <mine>`
and affects zero rows once the lease has moved on.

Also here: `failed` joins the unique index predicate. A failed period must be
retryable, but by reclaiming the row that still holds its cursor and totals —
not by inserting a second row that would silently restart the traversal from
the beginning. With `failed` inside the index there is exactly one logical row
per (task, period) and retry can only be an UPDATE.

And `snapshot_at`: the traversal's immutable upper boundary. The sweep
selectors are re-evaluated on every page, so without a boundary a busy database
could keep extending the current run. Rows created after the run started wait
for the next period.

`started_at` gains its model-side default; the database already had one, and
the ORM was inserting an explicit NULL over it.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0037_cron_lease"
down_revision = "0036_cron_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 'skipped_already_completed' is 25 characters and did not fit.
    op.alter_column("cron_runs", "status",
                    existing_type=sa.String(16), type_=sa.String(32),
                    existing_nullable=False)

    stamp = sa.DateTime(timezone=True)
    op.add_column("cron_runs",
                  sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("cron_runs", sa.Column("lease_acquired_at", stamp, nullable=True))
    op.add_column("cron_runs", sa.Column("lease_expires_at", stamp, nullable=True))
    op.add_column("cron_runs", sa.Column("snapshot_at", stamp, nullable=True))

    # Taking over an abandoned lease is a hot path on a table that grows one
    # row per task per period; keep it an index lookup.
    op.create_index("ix_cron_runs_lease", "cron_runs", ["task", "period", "lease_expires_at"])

    # `failed` joins the claim predicate so a retry reclaims the existing row
    # instead of starting a second logical run for the same period.
    op.drop_index("uq_cron_runs_task_period_claim", table_name="cron_runs")
    op.create_index(
        "uq_cron_runs_task_period_claim", "cron_runs", ["task", "period"],
        unique=True,
        postgresql_where=sa.text(
            "period IS NOT NULL "
            "AND status IN ('running', 'continuing', 'failed', 'ok')"))


def downgrade() -> None:
    op.drop_index("uq_cron_runs_task_period_claim", table_name="cron_runs")
    op.create_index(
        "uq_cron_runs_task_period_claim", "cron_runs", ["task", "period"],
        unique=True,
        postgresql_where=sa.text(
            "period IS NOT NULL AND status IN ('running', 'continuing', 'ok')"))
    op.drop_index("ix_cron_runs_lease", table_name="cron_runs")
    op.drop_column("cron_runs", "snapshot_at")
    op.drop_column("cron_runs", "lease_expires_at")
    op.drop_column("cron_runs", "lease_acquired_at")
    op.drop_column("cron_runs", "lease_token")
    # Truncate anything that would not fit before narrowing the column back.
    op.execute("UPDATE cron_runs SET status = left(status, 16)")
    op.alter_column("cron_runs", "status",
                    existing_type=sa.String(32), type_=sa.String(16),
                    existing_nullable=False)
