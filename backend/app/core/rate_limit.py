"""Redis fixed-window rate limiting (synchronous, fail-open).

Added per Architecture §8/Q11 and PRD §8 — the source spec has no rate limiting,
leaving registration/auth open to flooding. A simple fixed-window counter keyed by
client IP + route bucket.

Sync client: our API endpoints are sync `def`, run in a threadpool — a sync Redis
client avoids event-loop lifecycle issues. If Redis is unavailable the limiter
**fails open** (logs and allows) so a Redis outage can't take down auth.
"""

from __future__ import annotations

import redis
from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError
from app.core.logging import get_logger

log = get_logger("rate_limit")

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        # Timeouts are load-bearing, not tuning. Failing open is the design, but
        # the *default* client waits ~4s before deciding it cannot connect, and
        # that wait lands on every rate-limited request: voting, reporting,
        # commenting, and every auth call including OTP. Measured 2026-08-10 with
        # no Redis listening: 4.045s per call. A dead limiter must cost
        # milliseconds, otherwise a Redis outage silently becomes a site-wide
        # four-second tax on exactly the endpoints users feel most.
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )
    return _redis


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, bucket: str,
                       max_requests: int | None = None,
                       window_seconds: int | None = None) -> None:
    """Increment the window counter; raise RateLimitError when exceeded."""
    max_requests = max_requests or settings.auth_rate_limit_max
    window_seconds = window_seconds or settings.auth_rate_limit_window_seconds
    key = f"rl:{bucket}:{_client_key(request)}"
    try:
        r = get_redis()
        current = r.incr(key)
        if current == 1:
            r.expire(key, window_seconds)
        ttl = r.ttl(key) if current > max_requests else 0
    except redis.RedisError as exc:  # fail open — never block auth on a Redis outage
        log.info("rate limiter unavailable; allowing", extra={
            "extra_fields": {"bucket": bucket, "error": str(exc)}})
        return
    if current > max_requests:
        raise RateLimitError(
            f"Rate limit exceeded for {bucket}. Retry in {max(ttl, 0)}s.",
            extra={"retry_after_seconds": max(ttl, 0)},
        )


def auth_rate_limiter(bucket: str):
    """Dependency factory for auth-adjacent endpoints."""

    def _dep(request: Request) -> None:
        enforce_rate_limit(request, bucket)

    return _dep
