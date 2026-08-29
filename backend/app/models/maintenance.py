"""Scheduled maintenance: run history, execution leases and the credential.

THE STATE MACHINE. Two things are tracked here, and conflating them is what
made the first design unsafe, so they are separate columns:

  LOGICAL RUN STATE — `status`. What is true of the period's WORK.
      running     claimed, in flight, no batch persisted yet
      continuing  incomplete, progress persisted, not currently executing
      failed      incomplete, progress preserved, retryable
      ok          complete (terminal)

  EXECUTION OWNERSHIP — the lease columns. WHO, if anyone, is running it now.
      lease_token set AND lease_expires_at in the future   -> executing
      lease_token NULL                                     -> idle, resumable
      lease_expires_at in the past                         -> abandoned

`continuing` therefore means "incomplete but idle", never "currently running",
which is what lets the very next scheduler call resume it with no delay.

Every mutation of a claimed row is conditioned on `lease_token = <mine>`. That
is the fencing guarantee: a request that stalled past its lease expiry, was
taken over, and then woke up will match zero rows and cannot overwrite the
newer owner's cursor.

The `skipped_*` rows are audit only. They record that the scheduler called and
was turned away; they hold no lease and stay outside the unique index.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class CronRun(Base, UUIDPrimaryKey, Timestamps):
    """One logical run of a scheduled maintenance task, or one audit note.

    Deliberately small. It answers "did the automation run, and did it work?"
    and nothing else: no payloads, no tracebacks, no identifiers of the rows
    touched. `failure` carries an exception CLASS, never a message, because a
    message can carry row data into a table moderators can read.
    """

    __tablename__ = "cron_runs"
    __table_args__ = (
        # ONE LOGICAL ROW PER (task, period), for the life of that period.
        #
        # `failed` is inside the predicate deliberately. A failed period must be
        # retryable, but it must be retried by RECLAIMING this row — which still
        # carries the cursor and processed_total of the work already done — not
        # by inserting a second row that would restart from the beginning and
        # lose the accounting. Retry is an UPDATE; the index makes that the only
        # option.
        #
        # The `skipped_*` audit rows stay outside it: a skip is a note that the
        # scheduler called, not a claim on the period.
        Index("uq_cron_runs_task_period_claim", "task", "period", unique=True,
              postgresql_where=text(
                  "period IS NOT NULL "
                  "AND status IN ('running', 'continuing', 'failed', 'ok')")),
        # Taking over an abandoned lease runs on every scheduler call; keep it
        # an index lookup rather than a scan of the run history.
        Index("ix_cron_runs_lease", "task", "period", "lease_expires_at"),
    )

    task: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Logical execution period in Asia/Manila — "2026-08-29" for a daily job,
    #: "2026-08" for a monthly one. Eligibility is decided from this rather than
    #: from the wall clock, so a scheduler that fires late still completes the
    #: period it missed instead of skipping it.
    period: Mapped[str | None] = mapped_column(String(16), index=True)
    #: When this period was due to run, so "late" is measurable.
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: "scheduler" or "manual". Both take the same service path, so this is the
    #: only difference worth recording.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduler")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: LOGICAL state — see the module docstring. Wide enough for the longest
    #: value ('skipped_already_completed', 25 characters); the original 16 was
    #: too narrow and truncated on insert.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    #: Records handled by the most recent invocation.
    processed: Mapped[int | None] = mapped_column(Integer)
    failure: Mapped[str | None] = mapped_column(String(64))
    #: A short, non-sensitive note — "not due today (Manila)", "already running".
    detail: Mapped[str | None] = mapped_column(String(200))

    # --- Resumable traversal ------------------------------------------------
    #: Last key durably completed, as text. The traversal key is always an
    #: immutable primary key, never a score or timestamp the sweep itself
    #: rewrites.
    cursor: Mapped[str | None] = mapped_column(String(64))
    #: Records handled across every invocation of this period, not just the last.
    processed_total: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0)
    #: The traversal's immutable upper boundary: only rows that existed when the
    #: logical run was created are in scope. Without it a busy database could
    #: extend a sweep indefinitely, because the selectors are re-evaluated on
    #: every page. Rows created after this wait for the next period.
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Execution ownership (the lease) ------------------------------------
    #: Fencing token. Every write by an executing request is conditioned on it,
    #: so a stalled request cannot overwrite the state of whoever took over.
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: When this lease becomes stealable. Comfortably longer than any budgeted
    #: request, so a healthy invocation can never be preempted mid-flight.
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Retained for history; the lease columns are what decide ownership.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
