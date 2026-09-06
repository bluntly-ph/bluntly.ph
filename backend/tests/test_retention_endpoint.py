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
    """The handler is `RetentionSweepResult(**run_retention_sweep(db))`.

    The shape was wrong once — the model claimed three fields for two — and a
    response model that does not match its service is a 500 the first time
    somebody calls it. Task 9 then widened the sweep to also report four
    telemetry purge counts, which the model does not surface but must still
    tolerate as extras.

    Driven through a fake session so the real return contract — the sweep's
    dict, and the handler building its response from it — is exercised with no
    database and no external effect. It parses no source and rebuilds none of
    the sweep's arithmetic: a renamed key, a dropped key, or a new required
    model field all make it fail.
    """
    from app.api.v1.routes.admin_earnings import RetentionSweepResult, run_pii_retention

    class _Result:
        rowcount = 0

    class _FakeSession:
        """What `run_retention_sweep` needs: `execute(...).rowcount` and
        `commit()`. Every UPDATE/DELETE reports zero rows, so `bounded_purge`
        stops after one empty batch and nothing leaves the process."""

        def execute(self, *_args, **_kwargs):
            return _Result()

        def commit(self):
            pass

    counts = run_retention_sweep(_FakeSession())

    # Every field the response model requires must be produced by the sweep, or
    # `RetentionSweepResult(**counts)` is the promised 500.
    missing = set(RetentionSweepResult.model_fields) - counts.keys()
    assert not missing, f"the sweep never returns {sorted(missing)}, which the model requires"

    # The two session-PII keys and Task 9's four telemetry purge counts are the
    # documented return contract; renaming or dropping any of them breaks here.
    assert {"hashed", "purged", "reading_sessions", "review_view_buckets",
            "request_geo_buckets", "first_vote_geo_buckets"} <= counts.keys(), (
        f"the sweep's return contract changed: {sorted(counts)}")

    # The handler builds its response from that dict without a 500, and the
    # extra telemetry keys are dropped rather than leaked or rejected.
    result = run_pii_retention(db=_FakeSession(), mod=None)
    assert isinstance(result, RetentionSweepResult)
    assert result.model_dump().keys() == RetentionSweepResult.model_fields.keys()


def test_the_sweep_is_idempotent_by_construction():
    """It selects on deadlines, so a second run finds nothing left to do."""
    src = inspect.getsource(run_retention_sweep)
    assert "ip_hash_at <= :now" in src and "ip_address IS NOT NULL" in src, (
        "the sweep no longer filters on a deadline plus remaining work, so "
        "running it twice may not be a no-op")
