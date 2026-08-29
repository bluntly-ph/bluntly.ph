"""automated scheduled maintenance: run history and scheduler credential

Until now the eight periodic jobs existed only as Celery beat entries, and
Celery beat was never deployed — worker and beat are defined solely in
backend/docker-compose.yml, a development file. Vercel hosts the frontend and
the FastAPI service; nothing ran the schedule. Every periodic responsibility,
including PII retention, depended on a moderator remembering to press a button.

This adds the two tables the production scheduler needs.

`cron_runs` is the execution record: what ran, when, how it finished, how much
it processed. It is the observability that makes "is automation healthy?" a
question a moderator can answer, and it is deliberately small — no payloads, no
tracebacks, no credentials, and a failure is recorded as an exception CLASS
rather than a message, for the same reason the admin Overview's diagnostics
were: a message can carry row data.

`cron_credentials` holds a SHA-256 hash of the scheduler's shared secret, never
the secret. The scheduler (GitHub Actions) sends the secret in a header; the
API hashes what it receives and compares digests in constant time. The secret
itself lives only in the scheduler platform's secret store.

Why a table rather than an environment variable: the production application's
environment is managed by the hosting platform, and the deployment credential
for it is not available to this workflow. The database is a secret store the
application is already trusted with, and putting the hash there keeps the
plaintext out of source, out of the repository, and out of every log.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0034_scheduled_maintenance"
down_revision = "0033_review_view_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cron_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("task", sa.String(64), nullable=False, index=True),
        # "scheduler" or "manual" — a moderator pressing Run now and the
        # scheduler firing use the SAME service call, so the only difference
        # worth recording is who asked.
        sa.Column("source", sa.String(16), nullable=False, server_default="scheduler"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        # ok | failed | skipped | locked
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("processed", sa.Integer(), nullable=True),
        # Exception CLASS only. Never a message: a message can carry row data.
        sa.Column("failure", sa.String(64), nullable=True),
        sa.Column("detail", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_cron_runs_task_started", "cron_runs", ["task", "started_at"])

    op.create_table(
        "cron_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        # sha256 hex of the shared secret. The secret is never stored.
        sa.Column("secret_sha256", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cron_credentials")
    op.drop_index("ix_cron_runs_task_started", table_name="cron_runs")
    op.drop_table("cron_runs")
