"""Celery task bodies (M2).

Each task delegates to a service function that takes a Session, so the logic is
unit-testable without a worker. Commission reconciliation (§3.3) runs inline from
the admin CSV import endpoint; the task here exists for future async use.
"""

from __future__ import annotations

from contextlib import contextmanager

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

log = get_logger("worker.tasks")


@contextmanager
def _session():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.recompute_wilson_scores")
def recompute_wilson_scores() -> dict:
    """Nightly re-decay of review wilson scores + product trust (M2 s2/s4)."""
    from app.services import trust_rating_service, vote_service

    with _session() as db:
        reviews_updated = vote_service.recompute_all_wilson_scores(db)
        trust_updated = trust_rating_service.recompute_all_trust_ratings(db)
    result = {"status": "ok", "task": "recompute_wilson_scores",
              "reviews_updated": reviews_updated, **trust_updated}
    log.info("wilson recompute done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.schedule_payouts")
def schedule_payouts() -> dict:
    """Monthly: reserve wallet balances into payouts, tier-priority first, and
    hand the batch to the provider (M3 slice 11). With no credentials the batch
    stays `scheduled` for the manual rail — never a crash."""
    from app.services.payout_service import schedule_payouts as _schedule
    from app.services.payout_service import submit_batch

    with _session() as db:
        result = _schedule(db)
        if result["scheduled"]:
            result["submission"] = submit_batch(db, result["batch_id"])
    log.info("payout scheduling done", extra={"extra_fields": result})
    return {"status": "ok", "task": "schedule_payouts", **result}


@celery_app.task(name="app.workers.tasks.refresh_payout_batches")
def refresh_payout_batches() -> dict:
    """Daily: poll in-flight batches and settle them (paid / failed+refunded)."""
    from sqlalchemy import select

    from app.models.enums import PayoutStatus
    from app.models.payout import Payout
    from app.services.payout_service import refresh_batch

    results = []
    with _session() as db:
        batches = db.scalars(select(Payout.batch_id).where(
            Payout.status == PayoutStatus.processing).distinct()).all()
        for batch in batches:
            if batch:
                results.append(refresh_batch(db, batch))
    result = {"status": "ok", "task": "refresh_payout_batches",
              "batches": len(results), "results": results}
    log.info("payout batch refresh done", extra={"extra_fields": {"batches": len(results)}})
    return result


@celery_app.task(name="app.workers.tasks.sweep_contracts")
def sweep_contracts() -> dict:
    """Daily: active contracts past term auto-renew, or expire (M3 slice 10)."""
    from app.services.contract_service import sweep_contracts as _sweep

    with _session() as db:
        counts = _sweep(db)
    result = {"status": "ok", "task": "sweep_contracts", **counts}
    log.info("contract sweep done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.expire_requests")
def expire_requests() -> dict:
    """Daily: open requests past expires_at -> expired, escrow refunded (M3 s9)."""
    from app.services.request_service import expire_open_requests

    with _session() as db:
        expired = expire_open_requests(db)
    result = {"status": "ok", "task": "expire_requests", "expired": expired}
    log.info("request expiry sweep done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.recompute_all_trust")
def recompute_all_trust() -> dict:
    """Nightly trust progression sweep over recently-active users (M2 slice 3)."""
    from app.services.trust_service import recompute_recently_active_users

    with _session() as db:
        users_updated = recompute_recently_active_users(db)
    result = {"status": "ok", "task": "recompute_all_trust", "users_updated": users_updated}
    log.info("trust recompute done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.run_honesty_fund_distribution")
def run_honesty_fund_distribution(cycle_month: str | None = None) -> dict:
    """Monthly Honesty Fund pool computation & distribution (M2 slice 8).

    `cycle_month`: "YYYY-MM"; defaults to the previous calendar month
    (Asia/Manila). Idempotent — an already-distributed cycle aborts.
    """
    from datetime import date

    from app.services.honesty_fund_service import distribute

    cycle = None
    if cycle_month:
        year, month = cycle_month.split("-")
        cycle = date(int(year), int(month), 1)
    with _session() as db:
        result = distribute(db, cycle_month=cycle)
    result = {**result, "cycle_month": str(result["cycle_month"]),
              "task": "honesty_fund_distribution"}
    log.info("honesty fund distribution done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.run_pii_retention")
def run_pii_retention() -> dict:
    """Sessions PII retention sweep — IP hash @30d, IP+UA purge @90d (M2 slice 8)."""
    from app.services.retention_service import run_retention_sweep

    with _session() as db:
        counts = run_retention_sweep(db)
    result = {"status": "ok", "task": "pii_retention", **counts}
    log.info("pii retention sweep done", extra={"extra_fields": result})
    return result


@celery_app.task(name="app.workers.tasks.reconcile_commission_csv")
def reconcile_commission_csv(import_id: str) -> dict:
    """Commission reconciliation runs INLINE from the admin CSV import endpoint
    (monthly exports are small — see commission_service.import_commissions).
    This task is a seam for future async use (load a stored file by import id);
    intentionally a documented no-op until file storage exists (M3)."""
    log.info("commission_reconciliation invoked (inline-only; see admin import)",
             extra={"extra_fields": {"import_id": import_id}})
    return {"status": "inline_only", "task": "reconcile_commission_csv",
            "import_id": import_id}
