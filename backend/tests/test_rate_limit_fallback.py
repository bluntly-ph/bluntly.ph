"""The limiter must not go quiet when Redis is missing.

Measured against production on 2026-08-20: fourteen consecutive failed logins
from one address, all 401, not one 429, against a configured limit of ten per
minute. `REDIS_URL` was set nowhere, so every call reached for localhost,
raised `RedisError`, was logged at info, and was allowed.

Failing open was deliberate and remains right as a last resort. What was wrong
is that it was the *only* resort, so an unconfigured dependency silently became
"no rate limiting" - and nothing failed, which is why it lasted.

These tests pin the order: Redis, then Postgres, and only then open. They stub
both stores, so they need neither.
"""

from __future__ import annotations

import redis

from app.core import rate_limit
from app.core.errors import RateLimitError


class _Req:
    """Minimal stand-in for a Request with a known client address."""

    def __init__(self, ip: str = "203.0.113.9") -> None:
        self.headers = {"x-forwarded-for": ip}
        self.client = None


def _redis_is_down(monkeypatch):
    def boom():
        raise redis.ConnectionError("no redis configured")
    monkeypatch.setattr(rate_limit, "get_redis", boom)


def test_postgres_takes_over_when_redis_is_absent(monkeypatch):
    """The whole point: an unconfigured Redis must not mean no limit."""
    _redis_is_down(monkeypatch)
    monkeypatch.setattr(rate_limit, "_count_in_postgres", lambda k, w: (11, 42))

    try:
        rate_limit.enforce_rate_limit(_Req(), "login", max_requests=10)
    except RateLimitError as exc:
        assert "login" in str(exc)
        assert exc.extra["retry_after_seconds"] == 42
    else:
        raise AssertionError("11 requests against a limit of 10 was allowed")


def test_postgres_allows_a_request_inside_the_window(monkeypatch):
    _redis_is_down(monkeypatch)
    monkeypatch.setattr(rate_limit, "_count_in_postgres", lambda k, w: (3, 55))
    rate_limit.enforce_rate_limit(_Req(), "login", max_requests=10)  # no raise


def test_both_stores_down_still_allows(monkeypatch):
    """Availability wins as a last resort. A counter must never break login."""
    _redis_is_down(monkeypatch)
    monkeypatch.setattr(rate_limit, "_count_in_postgres", lambda k, w: None)
    rate_limit.enforce_rate_limit(_Req(), "login", max_requests=1)  # no raise


def test_both_stores_down_is_logged_loudly(monkeypatch):
    """It was logged at info before, which is why nobody noticed for weeks."""
    _redis_is_down(monkeypatch)
    monkeypatch.setattr(rate_limit, "_count_in_postgres", lambda k, w: None)

    seen = []
    monkeypatch.setattr(rate_limit.log, "warning",
                        lambda msg, **kw: seen.append(msg))
    rate_limit.enforce_rate_limit(_Req(), "login", max_requests=1)
    assert seen, "no warning was emitted for a completely absent limiter"


def test_postgres_is_not_consulted_while_redis_works(monkeypatch):
    """Redis stays the primary; the fallback is a fallback."""
    class _R:
        def incr(self, key): return 1
        def expire(self, key, s): return True
        def ttl(self, key): return 60

    monkeypatch.setattr(rate_limit, "get_redis", lambda: _R())
    called = []
    monkeypatch.setattr(rate_limit, "_count_in_postgres",
                        lambda k, w: called.append(k))
    rate_limit.enforce_rate_limit(_Req(), "login", max_requests=10)
    assert not called, "Postgres was queried even though Redis answered"


def test_the_key_separates_clients_and_buckets(monkeypatch):
    """One client's failed logins must not throttle everyone else's."""
    _redis_is_down(monkeypatch)
    keys = []
    monkeypatch.setattr(rate_limit, "_count_in_postgres",
                        lambda k, w: (keys.append(k), (1, 60))[1])
    rate_limit.enforce_rate_limit(_Req("198.51.100.1"), "login", max_requests=10)
    rate_limit.enforce_rate_limit(_Req("198.51.100.2"), "login", max_requests=10)
    rate_limit.enforce_rate_limit(_Req("198.51.100.1"), "otp_request", max_requests=10)
    assert len(set(keys)) == 3, f"keys collided: {keys}"


def test_a_missing_table_degrades_instead_of_erroring(monkeypatch):
    """Before 0028 is applied the table does not exist. That must not 500."""
    from sqlalchemy.exc import ProgrammingError

    class _S:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            raise ProgrammingError("relation does not exist", {}, Exception())

    monkeypatch.setattr("app.db.session.SessionLocal", lambda: _S())
    assert rate_limit._count_in_postgres("rl:login:1.2.3.4", 60) is None
