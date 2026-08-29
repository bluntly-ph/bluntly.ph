"""Scheduled maintenance: run history and the scheduler's credential."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class CronRun(Base, UUIDPrimaryKey, Timestamps):
    """One execution of a scheduled maintenance task.

    Deliberately small. It answers "did the automation run, and did it work?"
    and nothing else: no payloads, no tracebacks, no identifiers of the rows
    touched. `failure` carries an exception CLASS, never a message, because a
    message can carry row data into a table moderators can read.
    """

    __tablename__ = "cron_runs"
    __table_args__ = (
        # The whole mutual-exclusion mechanism. A period may have at most one
        # row that is finished or in flight; `failed` and the skips stay
        # outside it so a failed period can be retried and a skip is only a
        # note that the scheduler called.
        Index("uq_cron_runs_task_period_claim", "task", "period", unique=True,
              postgresql_where=text(
                  "period IS NOT NULL AND status IN ('running', 'continuing', 'ok')")),
    )

    task: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Logical execution period in Asia/Manila — "2026-08-29" for a daily job,
    #: "2026-08" for a monthly one. A partial unique index over
    #: (task, period) WHERE status='ok' is what stops one period being
    #: completed twice, whatever two racing runners believe.
    period: Mapped[str | None] = mapped_column(String(16), index=True)
    #: When this period was due to run, so "late" is measurable.
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: "scheduler" or "manual". Both take the same service path, so this is the
    #: only difference worth recording.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduler")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: ok | failed | skipped | locked
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    processed: Mapped[int | None] = mapped_column(Integer)
    failure: Mapped[str | None] = mapped_column(String(64))
    #: A short, non-sensitive note — "not due today (Manila)", "already running".
    detail: Mapped[str | None] = mapped_column(String(200))


class CronCredential(Base, UUIDPrimaryKey, Timestamps):
    """The scheduler's shared secret, stored as a SHA-256 hash.

    The plaintext lives only in the scheduler platform's secret store. The API
    hashes what arrives in the request header and compares digests in constant
    time, so neither the database nor this repository ever holds the secret.
    """

    __tablename__ = "cron_credentials"

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    secret_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
