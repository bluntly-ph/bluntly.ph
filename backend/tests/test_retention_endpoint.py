"""The PII retention schedule must not depend on infrastructure that is absent.

`celery_app.beat_schedule` runs the sweep at 03:00 daily. Nothing runs it: the
deployment is two Vercel services, frontend and backend, with no worker and no
beat, and the broker points at a Redis that is not configured — the same
unconfigured Redis that left auth rate limiting open.

Measured against production on 2026-08-21: 225 sessions, 29 holding a raw IP,
and three already past their 30-day hashing deadline. The 90-day deletions
begin falling due from late October.

So the sweep gets a manual trigger, for the same reason the Honesty Fund has
one: the retention schedule is a promise about people's data, and it should not
be waiting on a process nobody deployed.
"""

from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.main import app
from app.services.retention_service import run_retention_sweep


def route() -> APIRoute:
    matches = [r for r in app.routes
               if isinstance(r, APIRoute) and r.path.endswith("/pii-retention/run")]
    assert matches, "the retention trigger is gone"
    return matches[0]


def test_the_trigger_exists_and_is_a_post():
    assert "POST" in route().methods


def test_it_requires_a_moderator():
    """It reads and rewrites session PII, so it is not for anyone signed in."""
    import pathlib
    module = (pathlib.Path(__file__).resolve().parents[1]
              / "app" / "api" / "v1" / "routes" / "admin_earnings.py")
    text = module.read_text(encoding="utf-8")
    # The router itself is moderator-gated, and the handler names it again.
    assert 'dependencies=[Depends(require_role("moderator"))]' in text
    assert 'require_role("moderator")' in text.split("def run_pii_retention")[1][:400]


def test_the_response_model_matches_what_the_sweep_returns():
    """The shape was wrong once — the model claimed three fields for two.

    A response model that does not match its service is a 500 the first time
    somebody calls it, and nothing about writing it would have said so.
    """
    from app.api.v1.routes.admin_earnings import RetentionSweepResult

    returned = inspect.getsource(run_retention_sweep)
    keys = set()
    for line in returned.splitlines():
        if line.strip().startswith("return {"):
            keys = {part.split('"')[1] for part in line.split(":") if '"' in part}
    assert keys, "could not read the sweep's return keys"
    assert set(RetentionSweepResult.model_fields) == keys, (
        f"the endpoint declares {sorted(RetentionSweepResult.model_fields)} but "
        f"the sweep returns {sorted(keys)}")


def test_the_sweep_is_idempotent_by_construction():
    """It selects on deadlines, so a second run finds nothing left to do."""
    src = inspect.getsource(run_retention_sweep)
    assert "ip_hash_at <= :now" in src and "ip_address IS NOT NULL" in src, (
        "the sweep no longer filters on a deadline plus remaining work, so "
        "running it twice may not be a no-op")
