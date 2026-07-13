"""Celery application + beat schedule.

M0 wires the app, the broker/backend (Redis), and the periodic schedule for the
three spec-required jobs. The task BODIES are stubs here — the actual Honesty
Fund distribution, commission reconciliation, and PII retention logic land in M2.
Defining the schedule now keeps the M0 contract honest and the wiring testable.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "bluntly",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=30 * 60,
    timezone="Asia/Manila",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    # Monthly Honesty Fund distribution — 1st of the month, 02:00 (Asia/Manila).
    "honesty-fund-monthly": {
        "task": "app.workers.tasks.run_honesty_fund_distribution",
        "schedule": crontab(day_of_month="1", hour=2, minute=0),
    },
    # PII retention sweep — daily 03:00. Enforces the sessions 30/90-day schedule.
    "pii-retention-daily": {
        "task": "app.workers.tasks.run_pii_retention",
        "schedule": crontab(hour=3, minute=0),
    },
}
