"""Celery task stubs (M0).

Bodies are intentionally minimal — the real logic is M2 scope. Each logs and
returns a structured no-op so the scheduler and worker wiring are verifiable now.
Commission reconciliation (§3.3) will be triggered on-demand from the admin CSV
import endpoint (also M2), not on a beat schedule.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

log = get_logger("worker.tasks")


@celery_app.task(name="app.workers.tasks.run_honesty_fund_distribution")
def run_honesty_fund_distribution(cycle_month: str | None = None) -> dict:
    """Monthly Honesty Fund pool computation & distribution (M2 stub)."""
    log.info("honesty_fund_distribution invoked (stub)", extra={
        "extra_fields": {"cycle_month": cycle_month}})
    return {"status": "noop", "task": "honesty_fund_distribution", "cycle_month": cycle_month}


@celery_app.task(name="app.workers.tasks.run_pii_retention")
def run_pii_retention() -> dict:
    """Sessions PII retention sweep — UA purge @90d, IP hash @30d/delete @90d (M2 stub)."""
    log.info("pii_retention invoked (stub)")
    return {"status": "noop", "task": "pii_retention"}


@celery_app.task(name="app.workers.tasks.reconcile_commission_csv")
def reconcile_commission_csv(import_id: str) -> dict:
    """Idempotent commission CSV reconciliation, run off-request (M2 stub)."""
    log.info("commission_reconciliation invoked (stub)", extra={
        "extra_fields": {"import_id": import_id}})
    return {"status": "noop", "task": "reconcile_commission_csv", "import_id": import_id}
