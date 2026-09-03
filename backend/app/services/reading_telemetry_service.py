"""Pure collection helpers for privacy-preserving reading telemetry.

This module deliberately contains no scoring, payout, ranking, or persistence
logic. Client-provided telemetry is only reduced to bounded collection values.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

MAX_SESSION_MS = 1_800_000
MAX_CHECKPOINTS = 16
SKEW_TOLERANCE_MS = 5_000
SCROLL_MILESTONES = (0, 25, 50, 75, 100)
RETENTION_DAYS = 90
RETENTION_BATCH = 5_000
MAX_BATCHES_PER_RUN = 40


@dataclass(frozen=True)
class CheckpointData:
    """One client-asserted checkpoint; every value is a claim."""

    impression_id: uuid.UUID
    review_id: uuid.UUID
    seq: int
    active_ms: int
    body_active_ms: int
    wall_ms: int
    scroll_pct: int
    vote_after_ms: int | None
    report_after_ms: int | None
    comment_after_ms: int | None
    share_after_ms: int | None
    photo_after_ms: int | None
    outlink_after_ms: int | None


@dataclass(frozen=True)
class Clamped:
    """A checkpoint reduced to values accepted by database constraints."""

    active_ms: int
    body_active_ms: int
    wall_ms: int
    scroll_milestone: int
    clamped: bool


def snap_scroll(pct: int) -> int:
    """Return the deepest legal scroll milestone reached by ``pct``."""
    value = max(0, min(int(pct), 100))
    return max(milestone for milestone in SCROLL_MILESTONES if milestone <= value)


def device_class_from_user_agent(user_agent: str | None) -> int:
    """Derive 0 unknown, 1 phone, 2 tablet, or 3 desktop from a User-Agent."""
    ua = (user_agent or "").lower()
    if not ua:
        return 0
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return 2
    if any(token in ua for token in ("iphone", "ipod", "mobi", "android")):
        return 1
    if any(token in ua for token in ("mozilla", "webkit", "gecko", "trident")):
        return 3
    return 0


def clamp(checkpoint: CheckpointData, *, elapsed_ms: int | None = None) -> Clamped:
    """Bound client claims and state whether any value was changed."""
    dirty = False

    active = max(0, int(checkpoint.active_ms))
    if active != checkpoint.active_ms:
        dirty = True
    if active > MAX_SESSION_MS:
        active, dirty = MAX_SESSION_MS, True
    if elapsed_ms is not None:
        ceiling = max(0, int(elapsed_ms)) + SKEW_TOLERANCE_MS
        if active > ceiling:
            active, dirty = ceiling, True

    body = max(0, int(checkpoint.body_active_ms))
    if body != checkpoint.body_active_ms:
        dirty = True
    if body > active:
        body, dirty = active, True

    wall = max(0, int(checkpoint.wall_ms))
    if wall != checkpoint.wall_ms:
        dirty = True
    if wall > MAX_SESSION_MS:
        wall, dirty = MAX_SESSION_MS, True

    milestone = snap_scroll(checkpoint.scroll_pct)
    if milestone != checkpoint.scroll_pct:
        dirty = True

    return Clamped(
        active_ms=active,
        body_active_ms=body,
        wall_ms=wall,
        scroll_milestone=milestone,
        clamped=dirty,
    )
