"""Sessions PII retention sweep (M2 slice 8; Architecture §4), plus bounded
batched retention for the reading-telemetry tables (review integrity
telemetry phase 1, design §9.2).

Bulk SQL (not per-row Python): the schedule deadlines were precomputed on insert
(`ip_hash_at` / `ip_delete_at` / `ua_purge_at`), so each step is one UPDATE.
The 30-day hash uses Postgres' built-in sha256 over exactly the same
`{salt}:{ip}` string as `services.pii.hash_ip`, so the two stay interchangeable.

The telemetry tables are different: they are append/upsert-heavy and can reach
millions of rows, so a bare `DELETE ... WHERE <time_column> < :cutoff` risks an
unbounded, long-running statement. `bounded_purge` instead deletes in capped
batches, committing each one, so a scheduled run does bounded work and a
multi-day backlog is picked up incrementally rather than in one all-or-nothing
transaction.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Matches `request_geo_buckets`, `review_view_buckets`, and
#: `dashboard_service.RANGES` (design §9.2).
RETENTION_DAYS = 90
#: Rows deleted per DELETE statement.
RETENTION_BATCH = 5_000
#: Batches per table per scheduled run; bounds a run to 200,000 rows/table.
MAX_BATCHES_PER_RUN = 40

#: The only tables `bounded_purge` may touch, and the only time column it may
#: compare against, for each. Table and column names are interpolated into SQL
#: text (bind parameters cannot stand in for identifiers), so this allow-list —
#: not caller input — is what makes that safe: a caller can select *which* of
#: these four pairs to purge, never name an arbitrary table or column.
PURGE_TARGETS: dict[str, str] = {
    "review_reading_sessions": "started_at",
    "review_view_buckets": "bucket_start",
    "request_geo_buckets": "bucket_start",
    "review_first_vote_geo_buckets": "bucket_start",
}


class PurgeResult(NamedTuple):
    deleted: int
    ceiling_hit: bool


def bounded_purge(
    db: Session,
    table: str,
    time_column: str,
    cutoff: datetime,
    *,
    batch_size: int = RETENTION_BATCH,
    max_batches: int = MAX_BATCHES_PER_RUN,
) -> PurgeResult:
    """Delete rows with `time_column < cutoff` from `table`, in capped batches.

    Bounded and idempotent: at most `max_batches` DELETEs of `batch_size` rows
    each, one commit per batch. Re-running (e.g. the next scheduled sweep)
    deletes the next slice — the predicate is the cutoff itself, so there is no
    cursor to corrupt on a retry. `ceiling_hit` is true when this call used
    every batch it was allowed *and* the last of those batches was full,
    meaning more rows past the cutoff may remain for the next invocation.

    `table` and `time_column` must be an exact pair from `PURGE_TARGETS` — this
    is the allow-list that makes building the DELETE by string interpolation
    safe; `cutoff` and `batch_size` remain ordinary bound parameters.

    `batch_size` and `max_batches` are caller-overridable for tests, but the
    architectural maxima (5,000 and 40, whose product is the 200,000-row-per-
    table-per-run ceiling) are enforced here regardless of what a caller
    passes — an override outside `1..RETENTION_BATCH` / `1..MAX_BATCHES_PER_RUN`
    fails closed rather than silently clamping, so a caller error surfaces
    immediately instead of quietly running an oversized or no-op sweep.
    """
    if PURGE_TARGETS.get(table) != time_column:
        raise ValueError(f"{table}.{time_column} is not an allow-listed retention target")
    if not (0 < batch_size <= RETENTION_BATCH):
        raise ValueError(
            f"batch_size must be between 1 and {RETENTION_BATCH}, got {batch_size!r}"
        )
    if not (0 < max_batches <= MAX_BATCHES_PER_RUN):
        raise ValueError(
            f"max_batches must be between 1 and {MAX_BATCHES_PER_RUN}, got {max_batches!r}"
        )

    # PostgreSQL does not accept LIMIT on DELETE, so the batch is selected by a
    # subquery and the outer DELETE targets exactly those ids.
    stmt = text(
        f"""
        DELETE FROM {table}
        WHERE id IN (
            SELECT id FROM {table}
            WHERE {time_column} < :cutoff
            ORDER BY id
            LIMIT :batch
        )
        """
    )

    deleted_total = 0
    last_batch = 0
    batches_run = 0
    for _ in range(max_batches):
        last_batch = db.execute(stmt, {"cutoff": cutoff, "batch": batch_size}).rowcount or 0
        db.commit()
        batches_run += 1
        deleted_total += last_batch
        if last_batch < batch_size:
            break

    ceiling_hit = batches_run >= max_batches and last_batch >= batch_size
    if ceiling_hit:
        # Table name and count only — never a row id, a reader reference, or a
        # location, so this is safe wherever scheduler logs end up.
        logger.warning(
            "retention ceiling hit for %s: %d rows deleted this run; more may remain",
            table, deleted_total,
        )
    return PurgeResult(deleted=deleted_total, ceiling_hit=ceiling_hit)


def run_retention_sweep(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Apply all due retention actions.

    Returns the existing session-PII keys plus one bounded-purge count per
    telemetry table, which `internal_cron._pii_retention` already sums
    unchanged into its `processed` total.
    """
    now = now or datetime.now(UTC)
    salt = settings.pii_hash_salt

    # >= 30d: replace the raw IP with a salted hash (matches pii.hash_ip).
    hashed = db.execute(
        text("""
            UPDATE sessions
            SET ip_hash = encode(sha256(convert_to(:salt || ':' || host(ip_address),
                                                   'UTF8')), 'hex'),
                ip_address = NULL
            WHERE ip_hash_at <= :now AND ip_address IS NOT NULL
        """),
        {"salt": salt, "now": now},
    ).rowcount

    # >= 90d: delete the hash too, and purge the user agent.
    purged_ip = db.execute(
        text("""
            UPDATE sessions
            SET ip_hash = NULL, ip_address = NULL
            WHERE ip_delete_at <= :now
              AND (ip_hash IS NOT NULL OR ip_address IS NOT NULL)
        """),
        {"now": now},
    ).rowcount
    purged_ua = db.execute(
        text("""
            UPDATE sessions
            SET user_agent = NULL
            WHERE ua_purge_at <= :now AND user_agent IS NOT NULL
        """),
        {"now": now},
    ).rowcount

    db.commit()

    cutoff = now - timedelta(days=RETENTION_DAYS)
    reading_sessions = bounded_purge(db, "review_reading_sessions", "started_at", cutoff)
    review_view_buckets = bounded_purge(db, "review_view_buckets", "bucket_start", cutoff)
    request_geo_buckets = bounded_purge(db, "request_geo_buckets", "bucket_start", cutoff)
    first_vote_geo_buckets = bounded_purge(
        db, "review_first_vote_geo_buckets", "bucket_start", cutoff)

    return {
        "hashed": hashed,
        "purged": purged_ip + purged_ua,
        "reading_sessions": reading_sessions.deleted,
        "review_view_buckets": review_view_buckets.deleted,
        "request_geo_buckets": request_geo_buckets.deleted,
        "first_vote_geo_buckets": first_vote_geo_buckets.deleted,
    }
