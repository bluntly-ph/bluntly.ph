"""Celery wiring (M1–M3 verification).

The beat schedule references tasks by STRING name. A typo, a rename, or a task
that raises on import is invisible until the scheduled hour arrives in
production and the job silently never runs — the Honesty Fund not paying out, or
PII never being purged (a legal obligation). These checks make that loud.
"""

from __future__ import annotations

import pytest

from app.workers.celery_app import celery_app
from tests.conftest import requires_db

# Every task the beat schedule fires, and what it must do when it runs.
SCHEDULED = {
    "app.workers.tasks.run_honesty_fund_distribution",
    "app.workers.tasks.run_pii_retention",
    "app.workers.tasks.recompute_wilson_scores",
    "app.workers.tasks.recompute_all_trust",
    "app.workers.tasks.expire_requests",
    "app.workers.tasks.sweep_contracts",
    "app.workers.tasks.schedule_payouts",
    "app.workers.tasks.refresh_payout_batches",
}


def test_every_beat_entry_points_at_a_registered_task():
    """A beat entry naming a task that isn't registered never runs — silently."""
    import app.workers.tasks  # noqa: F401  (registers the tasks)

    registered = set(celery_app.tasks)
    for name, entry in celery_app.conf.beat_schedule.items():
        task = entry["task"]
        assert task in registered, (
            f"beat entry {name!r} schedules {task!r}, which is NOT registered — "
            "it would never run in production")


def test_all_expected_tasks_are_scheduled():
    scheduled = {e["task"] for e in celery_app.conf.beat_schedule.values()}
    missing = SCHEDULED - scheduled
    assert missing == set(), f"tasks exist but nothing schedules them: {missing}"


def test_beat_schedules_are_valid_crontabs():
    from celery.schedules import crontab

    for name, entry in celery_app.conf.beat_schedule.items():
        assert isinstance(entry["schedule"], crontab), f"{name} has no crontab"


def test_timezone_is_manila():
    """Payout/fund cycles are month-boundary sensitive; a UTC beat would fire on
    the wrong local day."""
    assert celery_app.conf.timezone == "Asia/Manila"


@requires_db
@pytest.mark.parametrize("task_name", sorted(SCHEDULED))
def test_every_scheduled_task_actually_executes(task_name):
    """Run each task body for real against the DB. Unit tests cover the service
    functions; this covers the task wrapper — session handling, imports, and the
    return contract — which is what Celery actually invokes."""
    import app.workers.tasks  # noqa: F401

    task = celery_app.tasks[task_name]
    result = task.apply()          # eager, in-process; real DB, no broker needed
    assert result.successful(), f"{task_name} raised: {result.traceback}"
    assert isinstance(result.result, dict)
    assert "task" in result.result or "status" in result.result
