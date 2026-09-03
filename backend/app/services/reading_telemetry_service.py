"""Collection-only helpers and monotonic storage for reading telemetry.

Nothing here feeds scoring, payout, ranking, moderation, or publication. The
only persistence operation merges one bounded impression row in place.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Integer, and_, cast, extract, func, literal, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.enums import ReaderKind
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession

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
class ReaderIdentity:
    """Exactly one server-derived identity for a reading impression."""

    kind: ReaderKind
    reader_ref: uuid.UUID | None = None
    anon_ref: uuid.UUID | None = None


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


def _validate_identity(identity: ReaderIdentity) -> None:
    user = identity.kind == ReaderKind.user
    anon = identity.kind == ReaderKind.anon
    if not (
        (user and identity.reader_ref is not None and identity.anon_ref is None)
        or (anon and identity.anon_ref is not None and identity.reader_ref is None)
    ):
        raise ValueError("ReaderIdentity must contain exactly one matching identity")


def _normalize_country(country: str | None) -> str | None:
    value = (country or "").strip().upper()
    if (
        len(value) != 2
        or not value.isascii()
        or not value.isalpha()
        or value in {"XX", "ZZ"}
    ):
        return None
    return value


def _clamp_interaction(value: int | None) -> tuple[int | None, bool]:
    if value is None:
        return None, False
    bounded = max(0, min(int(value), MAX_SESSION_MS))
    return bounded, bounded != value


def record_checkpoint(
    db: Session,
    checkpoint: CheckpointData,
    identity: ReaderIdentity,
    *,
    country: str | None,
    user_agent: str | None,
) -> bool:
    """Validate, clamp, and monotonically merge one checkpoint.

    Return true only when the single INSERT/UPSERT changes one row. Replays,
    stale sequences, cross-reader/review collisions, and attempts beyond the
    checkpoint cap are full-row no-ops and therefore are not committed.
    """
    _validate_identity(identity)
    if not isinstance(checkpoint.impression_id, uuid.UUID):
        raise ValueError("impression_id must be a UUID")
    if checkpoint.impression_id.version != 4:
        raise ValueError("impression_id must be UUIDv4")
    if type(checkpoint.seq) is not int or not 0 <= checkpoint.seq <= 2_147_483_647:
        raise ValueError("seq must be a non-negative signed integer")

    review = db.get(Review, checkpoint.review_id)
    if review is None:
        raise NotFoundError("Review not found.")

    claimed = clamp(checkpoint)
    insert_bounded = clamp(checkpoint, elapsed_ms=0)
    interactions: dict[str, int | None] = {}
    interaction_clamped = False
    for source, target in (
        ("vote_after_ms", "vote_client_after_ms"),
        ("report_after_ms", "report_client_after_ms"),
        ("comment_after_ms", "comment_client_after_ms"),
        ("share_after_ms", "share_client_after_ms"),
        ("photo_after_ms", "photo_client_after_ms"),
        ("outlink_after_ms", "outlink_client_after_ms"),
    ):
        value, was_clamped = _clamp_interaction(getattr(checkpoint, source))
        interactions[target] = value
        interaction_clamped = interaction_clamped or was_clamped

    stmt = insert(ReviewReadingSession).values(
        impression_id=checkpoint.impression_id,
        review_id=checkpoint.review_id,
        reader_kind=identity.kind,
        reader_ref=identity.reader_ref,
        anon_ref=identity.anon_ref,
        last_seen_at=func.clock_timestamp(),
        active_ms=insert_bounded.active_ms,
        body_active_ms=insert_bounded.body_active_ms,
        wall_ms=insert_bounded.wall_ms,
        scroll_milestone=insert_bounded.scroll_milestone,
        checkpoints=1,
        max_seq=checkpoint.seq,
        clamped=insert_bounded.clamped or interaction_clamped,
        country=_normalize_country(country),
        word_count_at_view=len((review.discussion or "").split()),
        star_rating_at_view=review.star_rating,
        device_class=device_class_from_user_agent(user_agent),
        **interactions,
    )
    excluded = stmt.excluded
    claimed_active = literal(claimed.active_ms, type_=Integer())
    claimed_body = literal(claimed.body_active_ms, type_=Integer())
    elapsed_ms = cast(
        func.floor(
            extract(
                "epoch",
                excluded.last_seen_at - ReviewReadingSession.started_at,
            )
            * 1_000
        ),
        Integer,
    )
    allowed_active = func.least(
        MAX_SESSION_MS,
        func.greatest(0, elapsed_ms) + SKEW_TOLERANCE_MS,
    )
    elapsed_bounded_active = func.least(claimed_active, allowed_active)
    merged_active = func.greatest(
        ReviewReadingSession.active_ms,
        elapsed_bounded_active,
    )
    merged_body = func.greatest(
        ReviewReadingSession.body_active_ms,
        func.least(claimed_body, merged_active),
    )
    update_clamped = or_(
        ReviewReadingSession.clamped,
        literal(claimed.clamped or interaction_clamped),
        claimed_active > allowed_active,
        claimed_body > merged_active,
    )
    result = db.execute(
        stmt.on_conflict_do_update(
            index_elements=[ReviewReadingSession.impression_id],
            set_={
                "active_ms": merged_active,
                "body_active_ms": merged_body,
                "wall_ms": func.greatest(ReviewReadingSession.wall_ms, excluded.wall_ms),
                "scroll_milestone": func.greatest(
                    ReviewReadingSession.scroll_milestone, excluded.scroll_milestone
                ),
                "vote_client_after_ms": func.coalesce(
                    ReviewReadingSession.vote_client_after_ms,
                    excluded.vote_client_after_ms,
                ),
                "report_client_after_ms": func.coalesce(
                    ReviewReadingSession.report_client_after_ms,
                    excluded.report_client_after_ms,
                ),
                "comment_client_after_ms": func.coalesce(
                    ReviewReadingSession.comment_client_after_ms,
                    excluded.comment_client_after_ms,
                ),
                "share_client_after_ms": func.coalesce(
                    ReviewReadingSession.share_client_after_ms,
                    excluded.share_client_after_ms,
                ),
                "photo_client_after_ms": func.coalesce(
                    ReviewReadingSession.photo_client_after_ms,
                    excluded.photo_client_after_ms,
                ),
                "outlink_client_after_ms": func.coalesce(
                    ReviewReadingSession.outlink_client_after_ms,
                    excluded.outlink_client_after_ms,
                ),
                "checkpoints": ReviewReadingSession.checkpoints + 1,
                "max_seq": excluded.max_seq,
                "clamped": update_clamped,
                "last_seen_at": excluded.last_seen_at,
            },
            where=and_(
                ReviewReadingSession.review_id == excluded.review_id,
                ReviewReadingSession.reader_kind == excluded.reader_kind,
                ReviewReadingSession.reader_ref.is_not_distinct_from(excluded.reader_ref),
                ReviewReadingSession.anon_ref.is_not_distinct_from(excluded.anon_ref),
                ReviewReadingSession.max_seq < excluded.max_seq,
                ReviewReadingSession.checkpoints < MAX_CHECKPOINTS,
            ),
        )
    )
    changed = result.rowcount == 1
    if changed:
        db.commit()
    return changed
