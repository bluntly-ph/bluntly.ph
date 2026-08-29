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

The scheduler holds a shared secret; this route compares a SHA-256 of what
arrives against a hash stored in `cron_credentials`, in constant time. The
plaintext exists only in the scheduler's secret store — not in this repository,
not in the database, not in any log, and never in a URL.

Everything here is deliberately narrow:

  * only names in TASKS may be invoked; the path is not a function reference
  * a period is claimed by INSERTing a row that a unique index arbitrates,
    so an overlapping or retried invocation cannot double-run one. Advisory
    locks would NOT work here: the application connects through the Supabase
    transaction pooler, which hands a backend back at every commit, so a
    session-level lock can be released on a different connection than took it
  * every invocation is recorded in `cron_runs`, success or failure
  * failures record an exception CLASS, never a message
  * tasks whose real cadence is monthly carry a Manila-date guard, because the
    scheduler platform speaks UTC cron and "the 1st, 02:00 in Manila" is the
    last day of the previous month in UTC
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import MANILA
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.maintenance import CronCredential, CronRun

log = get_logger(__name__)

router = APIRouter(prefix="/internal/cron", tags=["internal: scheduled maintenance"])

CREDENTIAL_NAME = "scheduler"


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
    """Uses the retention policy already configured — no new duration here."""
    from app.services.retention_service import run_retention_sweep
    counts = run_retention_sweep(db) or {}
    return sum(int(v) for v in counts.values())


def _sweep_trust(db: Session, cursor: str | None, batch: int):
    """Full production population, traversed across invocations. No limit on
    who is eligible and no sampling — only where this batch stops."""
    from app.services.sweep_service import sweep_trust
    return sweep_trust(db, cursor, batch)


def _sweep_wilson(db: Session, cursor: str | None, batch: int):
    from app.services.sweep_service import sweep_wilson
    return sweep_wilson(db, cursor, batch)


def _refresh_payout_batches(db: Session) -> int:
    """Poll in-flight batches and settle them, exactly as the beat task did."""
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
    """Idempotent by design: an already-distributed cycle aborts."""
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

#: A claim older than this is treated as abandoned — the process that made it
#: died, and a serverless request cannot legitimately run for anything close to
#: this long. Without takeover one crash would block a task forever.
STALE_CLAIM = timedelta(minutes=30)

#: Distinct outcomes, so "nothing happened" is never ambiguous.
OK = "ok"
FAILED = "failed"
RUNNING = "running"
CONTINUING = "continuing"
NOT_DUE = "skipped_not_due"
ALREADY_DONE = "skipped_already_completed"
ALREADY_RUNNING = "skipped_already_running"


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
    """Claim this task's current period and do as much of it as fits.

    The claim is an INSERT arbitrated by a unique index, not an advisory lock.
    That is not a stylistic choice: the application connects through the
    Supabase transaction pooler, which hands the backend back at every commit,
    so a session-level advisory lock can be released on a different connection
    than acquired it — or never released at all. A row the database refuses to
    duplicate is mutual exclusion that pooling cannot undermine.

    The four refusals stay distinct, because collapsing them would hide a
    scheduler that had stopped behind one that was merely early.
    """
    spec = TASKS.get(task)
    if spec is None:
        # Do not echo the requested name into the response body.
        raise HTTPException(status_code=404, detail="Unknown maintenance task.")

    now = datetime.now(MANILA)
    period = spec.period(now)
    due_at = spec.threshold(now)

    if not spec.is_due(now):
        _record(db, task, source, NOT_DUE, period, due_at,
                detail=f"due {due_at:%Y-%m-%d %H:%M} Manila")
        return CronResult(task=task, status=NOT_DUE, period=period,
                          detail="not due yet")

    claim = _claim(db, task, source, period, due_at)
    if claim is None:
        # Someone holds it, or it is already finished. `_claim` distinguishes
        # the two by reading back the row that blocked the insert.
        existing = _existing(db, task, period)
        status = ALREADY_DONE if existing == OK else ALREADY_RUNNING
        _record(db, task, source, status, period, due_at,
                detail="period already completed" if status == ALREADY_DONE
                else "another runner holds this task")
        return CronResult(task=task, status=status, period=period,
                          detail="already completed" if status == ALREADY_DONE
                          else "already running")

    started = datetime.now(MANILA)
    try:
        if spec.resumable:
            result = spec.sweep(db, claim.cursor, spec.batch)
            total = (claim.processed_total or 0) + result.processed
            if result.complete:
                _finish(db, claim, OK, cursor=None, processed=result.processed,
                        total=total, started=started)
                log.info("scheduled sweep complete",
                         extra={"extra_fields": {"task": task, "period": period,
                                                 "processed_total": total}})
                return CronResult(task=task, status=OK, period=period,
                                  processed=result.processed, processed_total=total,
                                  run_id=str(claim.id))
            _finish(db, claim, CONTINUING, cursor=result.cursor,
                    processed=result.processed, total=total, started=started)
            return CronResult(task=task, status=CONTINUING, period=period,
                              processed=result.processed, processed_total=total,
                              more=True, run_id=str(claim.id),
                              detail="more records remain")

        processed = spec.run(db)
        db.commit()
        _finish(db, claim, OK, cursor=None, processed=processed,
                total=processed, started=started)
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
        # Marking the claim failed releases the period: it falls out of the
        # unique index, so the next invocation may retry it.
        _finish(db, claim, FAILED, cursor=None, processed=0,
                total=claim.processed_total or 0, started=started, failure=failure)
        # The class, not the message: a message can carry row data.
        raise HTTPException(status_code=500,
                            detail=f"Task failed: {failure}") from exc


def _claim(db: Session, task: str, source: str, period: str,
           due_at: datetime) -> CronRun | None:
    """Take this period, or return None if someone already has it.

    Resuming counts as holding it: a `continuing` claim belonging to this task
    and period is handed straight back, which is how a multi-invocation sweep
    picks up where it stopped.
    """
    try:
        mine = db.scalar(
            select(CronRun).where(
                CronRun.task == task, CronRun.period == period,
                CronRun.status == CONTINUING).limit(1))
        if mine is not None:
            mine.status = RUNNING
            mine.claimed_at = datetime.now(MANILA)
            db.commit()
            return mine

        stale_before = datetime.now(MANILA) - STALE_CLAIM
        abandoned = db.scalar(
            select(CronRun).where(
                CronRun.task == task, CronRun.period == period,
                CronRun.status == RUNNING,
                CronRun.claimed_at < stale_before).limit(1))
        if abandoned is not None:
            # The process that claimed this died. A serverless request cannot
            # legitimately run this long, so take it over rather than letting
            # one crash block the task forever.
            abandoned.claimed_at = datetime.now(MANILA)
            db.commit()
            log.warning("took over an abandoned scheduler claim",
                        extra={"extra_fields": {"task": task, "period": period}})
            return abandoned

        run = CronRun(task=task, source=source, status=RUNNING, period=period,
                      scheduled_for=due_at, started_at=datetime.now(MANILA),
                      claimed_at=datetime.now(MANILA), processed_total=0)
        db.add(run)
        db.commit()
        return run
    except IntegrityError:
        # The unique index refused it: another runner claimed this period
        # between our read and our write. That is the mechanism working.
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
                CronRun.status.in_((RUNNING, CONTINUING, OK))).limit(1))
    except Exception:  # noqa: BLE001
        db.rollback()
        return None


def _finish(db: Session, run: CronRun, status: str, *, cursor: str | None,
            processed: int, total: int, started: datetime,
            failure: str | None = None) -> None:
    """Close out this invocation's slice of the claim. Never raises."""
    try:
        run.status = status
        run.cursor = cursor
        run.processed = processed
        run.processed_total = total
        run.finished_at = datetime.now(MANILA)
        run.failure = failure
        db.commit()
    except Exception:  # noqa: BLE001 - bookkeeping must not break the task
        db.rollback()
        log.exception("could not close scheduled run",
                      extra={"extra_fields": {"task": run.task, "status": status}})


def _record(db: Session, task: str, source: str, status: str,
            period: str | None = None, scheduled_for: datetime | None = None, *,
            processed: int | None = None, failure: str | None = None,
            detail: str | None = None,
            started: datetime | None = None) -> str:
    """Write a non-claiming history row — the skips. Never raises.

    These deliberately do not take part in the unique index: a skip is a note
    that the scheduler called, not a claim on the period.
    """
    try:
        now = datetime.now(MANILA)
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
