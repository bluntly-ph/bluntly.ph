"""The production scheduling entry point.

PRODUCTION SCHEDULING AUTHORITY: GitHub Actions -> this route.

Celery beat was never deployed. Worker and beat exist only in
backend/docker-compose.yml, a development file; production runs the Next.js
frontend and this FastAPI service on Vercel and nothing else. Every periodic
responsibility — including PII retention, which is a legal obligation — was
therefore waiting on a moderator to press a button.

Why not deploy Celery: it would mean a persistent worker, a persistent beat and
a Redis broker, three new always-on services and their cost, to run eight jobs
that between them do a few seconds of work a day. The workload does not justify
the architecture. A scheduler that makes an authenticated HTTP call into the
service that already has the database connection does.

Why not Vercel Cron: this project is on the hobby plan, which allows two cron
entries at daily granularity. There are eight jobs across six cadences.


THE STATE MACHINE
-----------------

Two independent things, deliberately not conflated (see app/models/maintenance):

  LOGICAL RUN STATE — `status`, one row per (task, period), forever:

      (none) -> running -> ok            finished in one invocation
             -> running -> continuing    incomplete, idle, resumable
             -> running -> failed        incomplete, idle, progress preserved

  EXECUTION OWNERSHIP — the lease:

      lease_token set, lease_expires_at future  -> someone is executing it
      lease_token NULL                          -> idle, claimable NOW
      lease_expires_at past                     -> abandoned, stealable

`continuing` is "incomplete but idle", so the scheduler's very next call
resumes it immediately. There is no waiting period on the normal path; lease
expiry only governs recovery from a request that died.

Transitions, and what each returns to the scheduler:

    no row, due                -> claim (INSERT)          -> ok | continuing
    continuing, lease NULL     -> reclaim (UPDATE)        -> ok | continuing
    failed, lease NULL         -> reclaim (UPDATE)        -> ok | continuing
    running, lease live        -> refused                 -> already_running
    running, lease expired     -> steal (UPDATE, fenced)  -> ok | continuing
    ok                         -> refused                 -> already_completed
    not yet due                -> refused                 -> not_due

WHY NOT ADVISORY LOCKS. The application connects through the Supabase
TRANSACTION pooler — documented in app/db/session.py, because the session
pooler accepts only about four concurrent clients. PgBouncer in transaction
mode hands the backend back at every commit, so a session-level lock taken in
one transaction can be released on a different backend, or not at all. The
sweep services commit internally, several times. A dedicated SQLAlchemy
connection would not help, because the multiplexing is beneath SQLAlchemy.

So ownership is a lease taken by ONE conditional UPDATE. The database picks the
winner: a second runner blocks on the row lock, re-evaluates the predicate once
the first commits, sees a live lease, and matches zero rows. Single statement,
single transaction — exactly the property pooling cannot undermine.

FENCING. Every write an executing request makes is conditioned on
`lease_token = <mine>`. A request that stalled past its expiry, was taken over,
and then woke up matches zero rows and cannot overwrite the newer owner's
cursor. Without this, time-based takeover would be a data-loss mechanism.

Everything here is deliberately narrow:

  * only names in TASKS may be invoked; the path is not a function reference
  * the caller supplies no cursor, offset or batch size — the backend owns
    progression entirely, so the credential cannot be used to skip a population
  * every invocation is recorded in `cron_runs`, success, refusal or failure
  * failures record an exception CLASS, never a message
  * monthly jobs are evaluated by logical PERIOD, not by "is today the 1st",
    so a scheduler that misses a day still completes the period
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import MANILA
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.maintenance import CronCredential, CronRun

log = get_logger(__name__)

router = APIRouter(prefix="/internal/cron", tags=["internal: scheduled maintenance"])

CREDENTIAL_NAME = "scheduler"


# --- Time budget -------------------------------------------------------------
#
# CONSERVATIVE APPLICATION BUDGET — NOT A CLAIMED PLATFORM MAXIMUM.
#
# What is actually known: the Vercel team is on the **hobby** plan (read from
# the platform, not assumed). What could NOT be read: the per-function duration
# ceiling for this deployment — the project is not visible to the API token
# available here, and `vercel.json` sets no `maxDuration`, so the platform
# default applies and this code cannot see what that default is.
#
# So this is not derived from a ceiling. It is set BELOW the lowest duration
# limit Vercel has documented for Hobby, so that it holds whichever default is
# in force. Once the effective limit is confirmed in the dashboard, raise it
# with SCHEDULER_REQUEST_BUDGET_SECONDS rather than editing this line.
#
# A too-small budget costs extra invocations. It never costs correctness: the
# cursor is persisted every batch and the traversal resumes exactly where it
# stopped.
_DEFAULT_BUDGET_SECONDS = 8.0
REQUEST_BUDGET = timedelta(
    seconds=float(os.getenv("SCHEDULER_REQUEST_BUDGET_SECONDS",
                            _DEFAULT_BUDGET_SECONDS)))

#: How long a lease is honoured before another runner may steal it.
#:
#: This must comfortably EXCEED the request budget, or a healthy invocation
#: could be preempted while it is still working — which is what the fencing
#: token would then have to clean up after, every night. At a 8s budget this is
#: a ~37x margin, which also covers request start-up, the final persist and the
#: HTTP response. Because one invocation cannot approach the lease lifetime,
#: no lease heartbeat is needed; shortening the workload is the simpler bound.
LEASE = timedelta(minutes=5)


class Budget:
    """Wall-clock allowance for one invocation's processing.

    Monotonic, so a clock adjustment cannot extend or collapse it.
    """

    __slots__ = ("deadline",)

    def __init__(self, allowance: timedelta = REQUEST_BUDGET):
        self.deadline = time.monotonic() + allowance.total_seconds()

    def spent(self) -> bool:
        return time.monotonic() >= self.deadline


#: TEST SEAM. Overrides every task's batch capacity so a multi-batch traversal
#: can be exercised against a handful of real records instead of hundreds.
#: Deliberately module state and NOT a request parameter — see the test that
#: asserts `run_task` accepts no cursor, offset or batch argument. A caller who
#: could choose the batch size could also choose to process one record and
#: report the period continuing forever.
_BATCH_OVERRIDE: int | None = None

#: Same seam for the time budget, so a test can prove the budget — not the
#: record count — is what stopped a batch.
_BUDGET_OVERRIDE: timedelta | None = None


def _now() -> datetime:
    return datetime.now(MANILA)


class TaskSpec:
    """One schedulable job: what it does, when its work belongs to, and whether
    it can finish inside a single request.

    CADENCE. GitHub Actions does not guarantee delivery — a scheduled workflow
    can be late, dropped, retried or overlapped. Keying eligibility off "is
    today the 1st in Manila" means one missed invocation postpones a monthly job
    by a month. So each job has a logical PERIOD ("2026-08-29" daily, "2026-08"
    monthly, always Asia/Manila) and a THRESHOLD, and eligibility is "the
    threshold has passed and this period is not already done or in flight" —
    which catches up instead of skipping.

    SHAPE. Some jobs are one set-based statement and finish in milliseconds.
    Others recompute a population one record at a time; CI measured the trust
    sweep at 82 minutes against ~7,000 users, which no serverless request
    survives. Those declare a `sweep`, and are traversed across as many
    invocations as it takes, the period completing only when the whole
    population has been covered.
    """

    def __init__(self, run=None, *, sweep=None, batch: int = 250,
                 cadence: str, hour: int, minute: int = 0,
                 day_of_month: int | None = None, note: str = ""):
        assert (run is None) != (sweep is None), "a task is either simple or a sweep"
        self.run = run
        self.sweep = sweep
        self.batch = batch
        self.cadence = cadence
        self.hour = hour
        self.minute = minute
        self.day_of_month = day_of_month
        self.note = note

    @property
    def resumable(self) -> bool:
        return self.sweep is not None

    def capacity(self) -> int:
        return _BATCH_OVERRIDE if _BATCH_OVERRIDE is not None else self.batch

    def period(self, now: datetime) -> str:
        """The logical run this invocation belongs to, in Manila."""
        local = now.astimezone(MANILA)
        return (local.strftime("%Y-%m") if self.cadence == "monthly"
                else local.strftime("%Y-%m-%d"))

    def threshold(self, now: datetime) -> datetime:
        """When the current period became due, in Manila."""
        local = now.astimezone(MANILA)
        day = self.day_of_month if self.cadence == "monthly" else local.day
        return local.replace(day=day, hour=self.hour, minute=self.minute,
                             second=0, microsecond=0)

    def is_due(self, now: datetime) -> bool:
        return now.astimezone(MANILA) >= self.threshold(now)


def _expire_requests(db: Session) -> int:
    from app.services.request_service import expire_open_requests
    return int(expire_open_requests(db) or 0)


def _sweep_contracts(db: Session) -> int:
    from app.services.contract_service import sweep_contracts
    result = sweep_contracts(db) or {}
    return int(result.get("renewed", 0)) + int(result.get("expired", 0))


def _pii_retention(db: Session) -> int:
    """Uses the retention policy already configured — no new duration here.

    Set-based: three UPDATE/DELETE statements over rows past their retention
    horizon, with no Python loop and no per-record round trip. It does not need
    the continuation protocol, and giving it one would be complexity for its
    own sake.
    """
    from app.services.retention_service import run_retention_sweep
    counts = run_retention_sweep(db) or {}
    return sum(int(v) for v in counts.values())


def _sweep_trust(db: Session, cursor, batch, snapshot_at, budget):
    """Full production population, traversed across invocations. No limit on
    who is eligible and no sampling — only where this batch stops."""
    from app.services.sweep_service import sweep_trust
    return sweep_trust(db, cursor, batch, snapshot_at, budget)


def _sweep_wilson(db: Session, cursor, batch, snapshot_at, budget):
    from app.services.sweep_service import sweep_wilson
    return sweep_wilson(db, cursor, batch, snapshot_at, budget)


def _refresh_payout_batches(db: Session) -> int:
    """Poll in-flight batches and settle them, exactly as the beat task did.

    Loops, but over DISTINCT batch ids that are currently processing — a
    handful at most, and bounded by how many batches can be in flight rather
    than by how many users exist.
    """
    from sqlalchemy import select as _select

    from app.models.enums import PayoutStatus
    from app.models.payout import Payout
    from app.services.payout_service import refresh_batch

    batches = db.scalars(_select(Payout.batch_id).where(
        Payout.status == PayoutStatus.processing).distinct()).all()
    refreshed = 0
    for batch in batches:
        if batch:
            refresh_batch(db, batch)
            refreshed += 1
    return refreshed


def _honesty_fund(db: Session) -> int:
    """Idempotent by design: an already-distributed cycle aborts.

    NOT resumable, deliberately. It divides a fixed pool proportionally across
    every eligible review — `payout = pool * score / total_score` — so it must
    see the whole population in one pass. A half-visible population would
    compute wrong shares for everyone, which is far worse than taking longer.
    Its size is bounded by honesty-fund-eligible reviews in one month, not by
    the user table.
    """
    from app.services.honesty_fund_service import distribute
    result = distribute(db) or {}
    return int(result.get("recipients", 0) or result.get("distributed", 0) or 0)


def _schedule_payouts(db: Session) -> int:
    """Reserve wallet balances into a payout batch — preparation only.

    DELIBERATE DIFFERENCE from the old beat task, which followed scheduling
    with `submit_batch`. Automating internal ledger preparation is safe;
    automating the hand-off to a payment provider is a different decision, and
    turning a step a moderator used to take into one that happens unattended is
    not something a scheduler change should do quietly. Submission stays where
    it already is: POST /admin/payouts/run, a moderator action, through the
    same service call.

    (Submission is externally blocked regardless — no sandbox credentials — but
    the reason this is preparation-only is the policy, not the blocker.)

    NOT resumable: it orders candidates by tier priority across the whole
    eligible set, and its population is users already above the payout
    threshold. Duplicate protection is the `uq_payout_user_batch` constraint,
    not this route.
    """
    from app.services.payout_service import schedule_payouts
    result = schedule_payouts(db) or {}
    return int(result.get("scheduled", 0) or 0)


#: The allow-list. A name not in here cannot be invoked, and the path segment
#: is matched against these keys rather than resolved to anything.
TASKS: dict[str, TaskSpec] = {
    "pii_retention": TaskSpec(
        _pii_retention, cadence="daily", hour=3, note="daily 03:00 Manila"),
    "recompute_wilson_scores": TaskSpec(
        sweep=_sweep_wilson, cadence="daily", hour=4, note="daily 04:00 Manila"),
    "recompute_all_trust": TaskSpec(
        sweep=_sweep_trust, cadence="daily", hour=4, minute=30,
        note="daily 04:30 Manila"),
    "sweep_contracts": TaskSpec(
        _sweep_contracts, cadence="daily", hour=5, note="daily 05:00 Manila"),
    "expire_requests": TaskSpec(
        _expire_requests, cadence="daily", hour=5, minute=30, note="daily 05:30 Manila"),
    "refresh_payout_batches": TaskSpec(
        _refresh_payout_batches, cadence="daily", hour=6, note="daily 06:00 Manila"),
    "honesty_fund_distribution": TaskSpec(
        _honesty_fund, cadence="monthly", day_of_month=1, hour=2,
        note="1st of the month, 02:00 Manila"),
    "schedule_payouts": TaskSpec(
        _schedule_payouts, cadence="monthly", day_of_month=5, hour=2, minute=30,
        note="5th of the month, 02:30 Manila"),
}

#: LOGICAL RUN STATE.
OK = "ok"
FAILED = "failed"
RUNNING = "running"
CONTINUING = "continuing"
#: States a new invocation may take over. `ok` is absent: it is terminal.
CLAIMABLE = (RUNNING, CONTINUING, FAILED)

#: REFUSALS. Distinct, so "nothing happened" is never ambiguous — a scheduler
#: that has stopped must not look like one that is merely early.
NOT_DUE = "skipped_not_due"
ALREADY_DONE = "skipped_already_completed"
ALREADY_RUNNING = "skipped_already_running"


@dataclass
class Claim:
    """Proof that this invocation owns the logical run, plus its progress."""

    id: uuid.UUID
    token: uuid.UUID
    cursor: str | None
    processed_total: int
    snapshot_at: datetime | None


class CronResult(BaseModel):
    task: str
    status: str
    period: str | None = None
    processed: int | None = None
    #: Total across every batch of this period, not just this invocation.
    processed_total: int | None = None
    #: True when the scheduler should call again to continue the traversal.
    more: bool = False
    detail: str | None = None
    run_id: str | None = None


def require_scheduler(
    db: Session = Depends(get_db),
    x_cron_key: str | None = Header(default=None, alias="X-Cron-Key"),
) -> None:
    """Authenticate the scheduler.

    The secret arrives in a header, never a query string, so it cannot end up
    in an access log or a browser history. Comparison is constant time, and a
    missing credential row fails closed.
    """
    if not x_cron_key:
        raise HTTPException(status_code=401, detail="Scheduler credential required.")

    try:
        row = db.scalar(select(CronCredential).where(
            CronCredential.name == CREDENTIAL_NAME,
            CronCredential.is_active.is_(True)))
    except Exception:  # noqa: BLE001 - table absent until migration 0034 is applied
        db.rollback()
        log.warning("scheduler credential table unavailable; refusing")
        raise HTTPException(
            status_code=503,
            detail="Scheduler credential is not configured.") from None

    if row is None:
        # Fail closed: no configured credential means nothing may run.
        raise HTTPException(status_code=503, detail="Scheduler credential is not configured.")

    presented = hashlib.sha256(x_cron_key.encode()).hexdigest()
    if not hmac.compare_digest(presented, row.secret_sha256):
        raise HTTPException(status_code=401, detail="Scheduler credential rejected.")


@router.post("/{task}", response_model=CronResult, dependencies=[Depends(require_scheduler)],
             summary="Run one scheduled maintenance task")
def run_task(
    task: str = Path(...),
    db: Session = Depends(get_db),
    source: str = "scheduler",
) -> CronResult:
    """Take the execution lease on this task's current period and do as much of
    it as the time budget allows.

    Note the signature: no cursor, no offset, no batch size. Progression is
    entirely the backend's, so possession of the scheduler credential does not
    confer the ability to steer or truncate a traversal.
    """
    spec = TASKS.get(task)
    if spec is None:
        # Do not echo the requested name into the response body.
        raise HTTPException(status_code=404, detail="Unknown maintenance task.")

    now = _now()
    period = spec.period(now)
    due_at = spec.threshold(now)

    if not spec.is_due(now):
        _record(db, task, source, NOT_DUE, period, due_at,
                detail=f"due {due_at:%Y-%m-%d %H:%M} Manila")
        return CronResult(task=task, status=NOT_DUE, period=period,
                          detail="not due yet")

    claim = _claim(db, task, source, period, due_at)
    if claim is None:
        existing = _existing(db, task, period)
        status = ALREADY_DONE if existing == OK else ALREADY_RUNNING
        _record(db, task, source, status, period, due_at,
                detail="period already completed" if status == ALREADY_DONE
                else "another runner holds the lease")
        return CronResult(task=task, status=status, period=period,
                          detail="already completed" if status == ALREADY_DONE
                          else "already running")

    budget = Budget(REQUEST_BUDGET if _BUDGET_OVERRIDE is None
                    else _BUDGET_OVERRIDE)
    try:
        if spec.resumable:
            result = spec.sweep(db, claim.cursor, spec.capacity(),
                                claim.snapshot_at, budget)
            total = claim.processed_total + result.processed

            if result.complete:
                _release(db, claim, OK, cursor=None,
                         processed=result.processed, total=total)
                log.info("scheduled sweep complete",
                         extra={"extra_fields": {"task": task, "period": period,
                                                 "processed_total": total}})
                return CronResult(task=task, status=OK, period=period,
                                  processed=result.processed, processed_total=total,
                                  run_id=str(claim.id))

            # Incomplete. Persist progress and RELEASE the lease: `continuing`
            # means idle, so the scheduler's next call resumes it at once
            # rather than waiting out an expiry.
            _release(db, claim, CONTINUING, cursor=result.cursor,
                     processed=result.processed, total=total)
            return CronResult(task=task, status=CONTINUING, period=period,
                              processed=result.processed, processed_total=total,
                              more=True, run_id=str(claim.id),
                              detail="more records remain")

        processed = spec.run(db)
        db.commit()
        _release(db, claim, OK, cursor=None, processed=processed, total=processed)
        log.info("scheduled maintenance ok",
                 extra={"extra_fields": {"task": task, "period": period,
                                         "processed": processed}})
        return CronResult(task=task, status=OK, period=period,
                          processed=processed, processed_total=processed,
                          run_id=str(claim.id))

    except Exception as exc:  # noqa: BLE001 - recorded and reported, never swallowed
        db.rollback()
        failure = type(exc).__name__
        log.exception("scheduled maintenance failed",
                      extra={"extra_fields": {"task": task, "period": period}})
        # PRESERVE PROGRESS. The cursor stays where the last completed batch
        # left it, so a retry resumes rather than restarting the population.
        # The batch that failed is rolled back and will be replayed; that is
        # safe because the per-record work is a recomputation from source data,
        # which lands on the same value however many times it runs.
        _release(db, claim, FAILED, cursor=claim.cursor, processed=0,
                 total=claim.processed_total, failure=failure)
        # The class, not the message: a message can carry row data.
        raise HTTPException(status_code=500,
                            detail=f"Task failed: {failure}") from exc


def _claim(db: Session, task: str, source: str, period: str,
           due_at: datetime) -> Claim | None:
    """Take the execution lease on this period, or None if someone holds it.

    Two statements, each atomic on its own; no read-then-write anywhere.
    """
    token = uuid.uuid4()
    now = _now()
    expires = now + LEASE

    try:
        # 1. RECLAIM an existing incomplete run whose lease is free or expired.
        #
        #    This single UPDATE is the arbitration. Two concurrent runners
        #    cannot both win: the second blocks on the row lock, re-reads the
        #    row after the first commits, finds `lease_expires_at` in the
        #    future, and updates nothing. `lease_expires_at IS NULL` is the
        #    normal continuation path — a released `continuing` row is
        #    claimable immediately, with no delay of any kind.
        row = db.execute(
            update(CronRun)
            .where(CronRun.task == task,
                   CronRun.period == period,
                   CronRun.status.in_(CLAIMABLE),
                   or_(CronRun.lease_expires_at.is_(None),
                       CronRun.lease_expires_at <= now))
            .values(status=RUNNING, lease_token=token, lease_acquired_at=now,
                    lease_expires_at=expires, claimed_at=now, failure=None)
            .returning(CronRun.id, CronRun.cursor, CronRun.processed_total,
                       CronRun.snapshot_at)
            .execution_options(synchronize_session=False)
        ).first()
        db.commit()
        if row is not None:
            return Claim(id=row[0], token=token, cursor=row[1],
                         processed_total=row[2] or 0, snapshot_at=row[3])

        # 2. No incomplete row to take over, so this period has either never
        #    run or is finished. Create it; the unique index decides.
        #
        #    `snapshot_at` is captured HERE, once per logical run, and is never
        #    rewritten — it is the traversal's fixed upper boundary.
        run = CronRun(task=task, source=source, status=RUNNING, period=period,
                      scheduled_for=due_at, started_at=now, claimed_at=now,
                      processed_total=0, snapshot_at=now,
                      lease_token=token, lease_acquired_at=now,
                      lease_expires_at=expires)
        db.add(run)
        db.commit()
        return Claim(id=run.id, token=token, cursor=None, processed_total=0,
                     snapshot_at=run.snapshot_at)

    except IntegrityError:
        # The unique index refused it: the period is complete, or another
        # runner created it between our UPDATE and our INSERT. Mechanism
        # working as designed.
        db.rollback()
        return None
    except Exception:  # noqa: BLE001 - tables absent before the migrations land
        db.rollback()
        log.exception("could not claim scheduled period",
                      extra={"extra_fields": {"task": task, "period": period}})
        return None


def _existing(db: Session, task: str, period: str) -> str | None:
    """The status of whatever already holds this period."""
    try:
        return db.scalar(
            select(CronRun.status).where(
                CronRun.task == task, CronRun.period == period,
                CronRun.status.in_((*CLAIMABLE, OK))).limit(1))
    except Exception:  # noqa: BLE001
        db.rollback()
        return None


def _release(db: Session, claim: Claim, status: str, *, cursor: str | None,
             processed: int, total: int, failure: str | None = None) -> bool:
    """Persist this invocation's progress and give up the lease. Never raises.

    THE FENCE. Every field is written by one UPDATE conditioned on our own
    lease token. If the lease has since been stolen — because this request
    stalled past its expiry — the WHERE matches nothing, we write nothing, and
    the newer owner's cursor survives untouched. An expired request cannot
    resurrect its own view of the world.
    """
    try:
        result = db.execute(
            update(CronRun)
            .where(CronRun.id == claim.id, CronRun.lease_token == claim.token)
            .values(status=status, cursor=cursor, processed=processed,
                    processed_total=total, finished_at=_now(), failure=failure,
                    lease_token=None, lease_acquired_at=None,
                    lease_expires_at=None)
            .execution_options(synchronize_session=False))
        db.commit()
        if result.rowcount != 1:
            # Not an error we can fix here, but it must never be silent: it
            # means this request ran past its lease and something else took the
            # work over.
            log.warning("scheduler write fenced out; a newer owner holds this run",
                        extra={"extra_fields": {"run_id": str(claim.id),
                                                "attempted_status": status}})
            return False
        return True
    except Exception:  # noqa: BLE001 - bookkeeping must not break the task
        db.rollback()
        log.exception("could not close scheduled run",
                      extra={"extra_fields": {"run_id": str(claim.id),
                                              "status": status}})
        return False


def _record(db: Session, task: str, source: str, status: str,
            period: str | None = None, scheduled_for: datetime | None = None, *,
            processed: int | None = None, failure: str | None = None,
            detail: str | None = None,
            started: datetime | None = None) -> str:
    """Write a non-claiming audit row — the refusals. Never raises.

    These take no lease and stay outside the unique index: a refusal is a note
    that the scheduler called and was turned away, not a claim on the period.
    They are what makes "the scheduler is alive but everything is already done"
    distinguishable from "the scheduler stopped calling".
    """
    try:
        now = _now()
        run = CronRun(task=task, source=source, status=status, period=period,
                      scheduled_for=scheduled_for,
                      started_at=started or now, finished_at=now,
                      processed=processed, processed_total=processed or 0,
                      failure=failure, detail=detail)
        db.add(run)
        db.commit()
        return str(run.id)
    except Exception:  # noqa: BLE001 - history must not break the task itself
        db.rollback()
        log.exception("could not record scheduled run",
                      extra={"extra_fields": {"task": task, "status": status}})
        return ""
