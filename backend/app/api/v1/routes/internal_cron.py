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
  * every task runs under a Postgres advisory lock, so an overlapping or
    retried invocation cannot double-run one
  * every invocation is recorded in `cron_runs`, success or failure
  * failures record an exception CLASS, never a message
  * tasks whose real cadence is monthly carry a Manila-date guard, because the
    scheduler platform speaks UTC cron and "the 1st, 02:00 in Manila" is the
    last day of the previous month in UTC
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.constants import MANILA
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.maintenance import CronCredential, CronRun

log = get_logger(__name__)

router = APIRouter(prefix="/internal/cron", tags=["internal: scheduled maintenance"])

CREDENTIAL_NAME = "scheduler"


class TaskSpec:
    """One schedulable job, and when its work belongs to.

    `run` returns the number of records it processed, so the run history says
    how much work happened rather than only that something did.

    The rest describes the CADENCE, because GitHub Actions does not guarantee
    delivery. A scheduled workflow can be late, dropped, retried or overlapped.
    Keying eligibility off "is today the 1st in Manila" means one missed
    invocation postpones a monthly job by a month — the scheduler quietly not
    doing the thing it exists for.

    So each job has a logical PERIOD ("2026-08-29" daily, "2026-08" monthly,
    always in Asia/Manila) and a THRESHOLD, the moment that period became due.
    Eligibility is then:

        the threshold has passed
        AND this period has no successful run yet
        AND nothing is running it right now

    which catches up rather than skipping: a run arriving on the 2nd still
    completes August, and the next one that day finds August already done.
    """

    def __init__(self, run: Callable[[Session], int], *,
                 cadence: str, hour: int, minute: int = 0,
                 day_of_month: int | None = None, note: str = ""):
        self.run = run
        self.cadence = cadence          # "daily" | "monthly"
        self.hour = hour
        self.minute = minute
        self.day_of_month = day_of_month
        self.note = note

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


def _recompute_trust(db: Session) -> int:
    """Full production semantics: every recently active user, no limit, no
    sampling. Only the CI tests bound the selection."""
    from app.services.trust_service import recompute_recently_active_users
    return int(recompute_recently_active_users(db) or 0)


def _recompute_wilson(db: Session) -> int:
    from app.services import trust_rating_service, vote_service
    reviews = int(vote_service.recompute_all_wilson_scores(db) or 0)
    products = trust_rating_service.recompute_all_trust_ratings(db) or {}
    return reviews + int(products.get("products_updated", 0))


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
        _recompute_wilson, cadence="daily", hour=4, note="daily 04:00 Manila"),
    "recompute_all_trust": TaskSpec(
        _recompute_trust, cadence="daily", hour=4, minute=30, note="daily 04:30 Manila"),
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

#: Stable per-task advisory lock ids. Postgres advisory locks are session-held
#: and cost nothing when uncontended, which is the cheapest correct way to stop
#: a retried or overlapping invocation from running a sweep twice.
_LOCK_NAMESPACE = 4713


def _lock_key(task: str) -> int:
    return int(hashlib.sha256(task.encode()).hexdigest()[:8], 16) % 2_147_483_647


#: Distinct outcomes, so "nothing happened" is never ambiguous.
OK = "ok"
FAILED = "failed"
NOT_DUE = "skipped_not_due"
ALREADY_DONE = "skipped_already_completed"
ALREADY_RUNNING = "skipped_already_running"


class CronResult(BaseModel):
    task: str
    status: str
    period: str | None = None
    processed: int | None = None
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
    """Run one job if its current period is due and has not already succeeded.

    The three refusals are distinct on purpose. "Not due" is a scheduler that
    fired early; "already completed" is the normal answer for every extra
    invocation inside a period, and the answer that makes daily triggering of a
    monthly job safe; "already running" is an overlap. Reporting all three as
    one "skipped" would hide a scheduler that had stopped working.
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

    # The period may already be done — by an earlier invocation today, or by
    # the run that was supposed to happen and did. This is what makes the
    # monthly jobs safe to trigger daily.
    if _completed(db, task, period):
        _record(db, task, source, ALREADY_DONE, period, due_at,
                detail="period already completed")
        return CronResult(task=task, status=ALREADY_DONE, period=period,
                          detail="already completed for this period")

    # One runner at a time. try_advisory_lock returns immediately rather than
    # queueing, so a retry overlapping a slow sweep is told so instead of
    # doubling the work or holding the request open.
    #
    # Session-scoped rather than transaction-scoped: the service functions
    # commit internally, and an xact lock would be released by the first of
    # those commits, part-way through the very sweep it is protecting. A
    # session lock is released in `finally`, and by the connection dropping if
    # the process dies — so a crash cannot leave it held forever either.
    got_lock = db.scalar(text("SELECT pg_try_advisory_lock(:ns, :key)"),
                         {"ns": _LOCK_NAMESPACE, "key": _lock_key(task)})
    if not got_lock:
        _record(db, task, source, ALREADY_RUNNING, period, due_at,
                detail="another runner holds this task")
        return CronResult(task=task, status=ALREADY_RUNNING, period=period,
                          detail="already running")

    started = datetime.now(MANILA)
    try:
        processed = spec.run(db)
        db.commit()
        run_id = _record(db, task, source, OK, period, due_at,
                         processed=processed, started=started)
        log.info("scheduled maintenance ok",
                 extra={"extra_fields": {"task": task, "period": period,
                                         "processed": processed}})
        return CronResult(task=task, status=OK, period=period,
                          processed=processed, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 - recorded and reported, never swallowed
        db.rollback()
        failure = type(exc).__name__
        log.exception("scheduled maintenance failed",
                      extra={"extra_fields": {"task": task, "period": period}})
        # No success row is written, so the period stays eligible and the next
        # scheduled invocation retries it.
        _record(db, task, source, FAILED, period, due_at,
                failure=failure, started=started)
        # The class, not the message: a message can carry row data.
        raise HTTPException(status_code=500,
                            detail=f"Task failed: {failure}") from exc
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:ns, :key)"),
                   {"ns": _LOCK_NAMESPACE, "key": _lock_key(task)})
        db.commit()


def _completed(db: Session, task: str, period: str) -> bool:
    """Has this task already succeeded for this period?

    The partial unique index on (task, period) WHERE status='ok' is the real
    guarantee; this is the cheap check that avoids doing the work first and
    discovering the conflict afterwards.
    """
    try:
        return db.scalar(
            select(CronRun.id).where(
                CronRun.task == task,
                CronRun.period == period,
                CronRun.status == OK).limit(1)) is not None
    except Exception:  # noqa: BLE001 - table absent before the migration lands
        db.rollback()
        return False


def _record(db: Session, task: str, source: str, status: str,
            period: str | None = None, scheduled_for: datetime | None = None, *,
            processed: int | None = None, failure: str | None = None,
            detail: str | None = None,
            started: datetime | None = None) -> str:
    """Write the run history row. Never raises into the caller's path.

    The unique index can reject a success row if two runners raced the same
    period. That is the index doing its job — the work is done either way —
    so it is swallowed here rather than turned into a 500.
    """
    try:
        now = datetime.now(MANILA)
        run = CronRun(task=task, source=source, status=status, period=period,
                      scheduled_for=scheduled_for,
                      started_at=started or now, finished_at=now,
                      processed=processed, failure=failure, detail=detail)
        db.add(run)
        db.commit()
        return str(run.id)
    except Exception:  # noqa: BLE001 - history must not break the task itself
        db.rollback()
        log.exception("could not record scheduled run",
                      extra={"extra_fields": {"task": task, "status": status}})
        return ""
