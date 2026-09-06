"""Owner-run, read-only CSV exporter for reading-telemetry research questions.

Same idiom as `scripts/check_invariants.py`: every mode is a bounded SELECT,
never an INSERT/UPDATE/DELETE, and it writes nothing except the one CSV file
named by `--output`. There is no HTTP route for this data (design §8) — this
script is the only read path, and it exists to be run by hand from a
developer's machine, not by any service.

Four modes, each answering one question from the tracking spec (design §10)
without building a persisted graph or exposing a new identity surface:

  readings       One row per review impression: engagement and geography
                 (country only), no reader identity column.
  vote-timing    Impressions that reached a first vote, with the server-
                 stamped `first_vote_at` / `active_ms_at_first_vote` fields
                 that answer "how much active reading came before the vote".
  relationships  Voter <-> reviewer overlap, derived on read from
                 `review_votes` over at most the author's 30 most recent
                 published reviews, all bound to --since-days. No edge table,
                 no voter identity beyond the id `review_votes` already stores.
  geo-summary    Identity-free hourly geography aggregates only: first-time
                 votes by place next to request traffic by the same place.

Usage:
    cd backend && python -m scripts.export_reading_telemetry \\
        --mode readings --since-days 30 --output /tmp/readings.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PureWindowsPath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import RequestGeoBucket, ReviewFirstVoteGeoBucket
from app.models.vote import ReviewVote
from app.services.ranking import wilson_lower_bound

MODES: tuple[str, ...] = ("readings", "vote-timing", "relationships", "geo-summary")

#: Matches retention: a range this tool could query but the data no longer
#: exists for would silently report an empty result and look like "no signal".
MIN_SINCE_DAYS = 1
MAX_SINCE_DAYS = 90
DEFAULT_SINCE_DAYS = MAX_SINCE_DAYS

#: Design §10: 20-30 recent published reviews per author. The brief's upper
#: bound, so the relationship query is always a bounded join, never a scan of
#: an author's full history.
RELATIONSHIP_WINDOW = 30

#: Names this tool refuses for --output because they are not a plain file on
#: disk: stdout/stderr/null aliases and the Windows reserved device names.
_FORBIDDEN_NAMES = {
    "-",
    "/dev/stdout", "/dev/stderr", "/dev/null", "/dev/fd/1", "/dev/fd/2",
}
_FORBIDDEN_PREFIXES = ("/dev/", "\\\\.\\", "\\\\?\\")

#: Windows reserved device names. Windows resolves these to the device
#: regardless of any extension, trailing text after the first '.', or trailing
#: dots/spaces (e.g. "NUL.csv", "nul." and "NUL " all open the NUL device), and
#: `CONIN$`/`CONOUT$` are matched by their literal names. Membership is checked
#: against the device token from `_device_name_token` below, never the raw
#: string. https://learn.microsoft.com/windows/win32/fileio/naming-a-file
_RESERVED_DEVICE_NAMES = {
    "con", "prn", "aux", "nul", "conin$", "conout$",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class OutputPathError(ValueError):
    """--output does not name a safe, writable, not-already-existing file."""


def _device_name_token(raw: str) -> str:
    """The name Windows would use to match a reserved device, computed
    identically on every host.

    `os.path.basename` is platform-dependent — on Linux (GitHub CI) it does not
    treat ``\\`` as a separator, so ``reports\\COM1.csv`` would slip through a
    Linux run. `PureWindowsPath` splits on *both* ``/`` and ``\\`` regardless of
    the OS executing this code, so the device check is deterministic in CI and
    on a developer's Windows box alike. Pure string inspection: no filesystem
    access, so a device name is never opened just by validating it.
    """
    name = PureWindowsPath(raw.strip()).name.lower()
    # Windows ignores any extension and trailing dots/spaces when matching a
    # device name; `CONIN$`/`CONOUT$` keep their '$' but take no extension.
    return name.split(".", 1)[0].strip(" .")


def _validate_output_path(raw: str) -> str:
    stripped = raw.strip()
    lowered = stripped.lower()
    name = PureWindowsPath(stripped).name.lower() if stripped else ""
    if (
        not stripped
        or lowered in _FORBIDDEN_NAMES
        or name in _FORBIDDEN_NAMES
        or lowered.startswith(_FORBIDDEN_PREFIXES)
        or _device_name_token(stripped) in _RESERVED_DEVICE_NAMES
    ):
        raise OutputPathError(
            f"--output must name a regular file path, not {raw!r}."
        )
    return stripped


def _since_days(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--since-days must be an integer, got {value!r}"
        ) from None
    if not (MIN_SINCE_DAYS <= parsed <= MAX_SINCE_DAYS):
        raise argparse.ArgumentTypeError(
            f"--since-days must be between {MIN_SINCE_DAYS} and {MAX_SINCE_DAYS}, got {parsed}"
        )
    return parsed


@dataclass(frozen=True)
class ExportResult:
    rows_written: int
    output_path: str


def _open_output(path: str):
    """Create the file exclusively. Refuses to silently overwrite anything."""
    try:
        return open(path, "x", newline="", encoding="utf-8")
    except FileExistsError:
        raise OutputPathError(
            f"{path} already exists; choose a new path or remove it first."
        ) from None


def _cutoff(since_days: int, now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(days=since_days)


READINGS_HEADER = [
    "review_id", "reader_kind", "country", "started_at", "active_ms",
    "body_active_ms", "wall_ms", "scroll_milestone", "checkpoints", "clamped",
    "first_vote_at", "active_ms_at_first_vote", "word_count_at_view",
    "star_rating_at_view", "device_class",
]


def export_readings(
    db: Session, output_path: str, *, since_days: int, now: datetime | None = None
) -> ExportResult:
    """One row per impression. No reader_ref/anon_ref/impression_id column —
    the point of this table is engagement research, not re-identifying a
    reader, so the export omits the columns that would let a CSV do that."""
    cutoff = _cutoff(since_days, now)
    stmt = (
        select(
            ReviewReadingSession.review_id,
            ReviewReadingSession.reader_kind,
            ReviewReadingSession.country,
            ReviewReadingSession.started_at,
            ReviewReadingSession.active_ms,
            ReviewReadingSession.body_active_ms,
            ReviewReadingSession.wall_ms,
            ReviewReadingSession.scroll_milestone,
            ReviewReadingSession.checkpoints,
            ReviewReadingSession.clamped,
            ReviewReadingSession.first_vote_at,
            ReviewReadingSession.active_ms_at_first_vote,
            ReviewReadingSession.word_count_at_view,
            ReviewReadingSession.star_rating_at_view,
            ReviewReadingSession.device_class,
        )
        .where(ReviewReadingSession.started_at >= cutoff)
        .order_by(ReviewReadingSession.started_at)
        .execution_options(stream_results=True)
    )
    rows_written = 0
    with _open_output(output_path) as handle:
        writer = csv.writer(handle)
        writer.writerow(READINGS_HEADER)
        for row in db.execute(stmt).yield_per(1000):
            writer.writerow([
                str(row.review_id),
                row.reader_kind.value,
                row.country or "",
                row.started_at.isoformat(),
                row.active_ms,
                row.body_active_ms,
                row.wall_ms,
                row.scroll_milestone,
                row.checkpoints,
                row.clamped,
                row.first_vote_at.isoformat() if row.first_vote_at else "",
                row.active_ms_at_first_vote if row.active_ms_at_first_vote is not None else "",
                row.word_count_at_view if row.word_count_at_view is not None else "",
                row.star_rating_at_view if row.star_rating_at_view is not None else "",
                row.device_class,
            ])
            rows_written += 1
    return ExportResult(rows_written=rows_written, output_path=output_path)


VOTE_TIMING_HEADER = [
    "review_id", "reader_kind", "country", "started_at", "first_vote_at",
    "active_ms_at_first_vote", "wall_ms", "seconds_to_first_vote",
]


def export_vote_timing(
    db: Session, output_path: str, *, since_days: int, now: datetime | None = None
) -> ExportResult:
    """Impressions that reached a first vote, server-stamped only.

    `first_vote_at` / `active_ms_at_first_vote` are written once, by the vote
    route, guarded so only the first vote on an impression can set them (design
    §9.1) — this mode simply reads that column pair rather than re-deriving it
    from a join, so it answers "how much active reading came before the vote"
    with no reconstruction logic to get wrong.
    """
    cutoff = _cutoff(since_days, now)
    stmt = (
        select(
            ReviewReadingSession.review_id,
            ReviewReadingSession.reader_kind,
            ReviewReadingSession.country,
            ReviewReadingSession.started_at,
            ReviewReadingSession.first_vote_at,
            ReviewReadingSession.active_ms_at_first_vote,
            ReviewReadingSession.wall_ms,
        )
        .where(
            ReviewReadingSession.started_at >= cutoff,
            ReviewReadingSession.first_vote_at.isnot(None),
        )
        .order_by(ReviewReadingSession.started_at)
        .execution_options(stream_results=True)
    )
    rows_written = 0
    with _open_output(output_path) as handle:
        writer = csv.writer(handle)
        writer.writerow(VOTE_TIMING_HEADER)
        for row in db.execute(stmt).yield_per(1000):
            seconds = (row.first_vote_at - row.started_at).total_seconds()
            writer.writerow([
                str(row.review_id),
                row.reader_kind.value,
                row.country or "",
                row.started_at.isoformat(),
                row.first_vote_at.isoformat(),
                row.active_ms_at_first_vote if row.active_ms_at_first_vote is not None else "",
                row.wall_ms,
                round(seconds, 3),
            ])
            rows_written += 1
    return ExportResult(rows_written=rows_written, output_path=output_path)


RELATIONSHIPS_HEADER = ["author_id", "voter_id", "voted", "eligible", "wilson_lower_bound"]


def export_relationships(
    db: Session, output_path: str, *, since_days: int, now: datetime | None = None
) -> ExportResult:
    """Voter <-> reviewer overlap, derived on read (design §10).

    No edge table. For each author with a review published in the window, look
    at only their `RELATIONSHIP_WINDOW` most recent published reviews *that are
    themselves inside the same `--since-days` window* and tally votes per voter
    over exactly that bounded set. An older review — one published before the
    cutoff — must not be pulled in just because the author also has one recent
    review, and neither must a vote whose own `created_at` predates the cutoff:
    both the review and the vote are independently window-bound, matching
    `fraud_service`'s "computed on read, bounded queries" posture.
    """
    cutoff = _cutoff(since_days, now)
    author_ids = db.execute(
        select(Review.author_id)
        .where(
            Review.author_id.isnot(None),
            Review.published_at.isnot(None),
            Review.published_at >= cutoff,
            Review.is_removed.is_(False),
        )
        .distinct()
    ).scalars().all()

    rows_written = 0
    with _open_output(output_path) as handle:
        writer = csv.writer(handle)
        writer.writerow(RELATIONSHIPS_HEADER)
        for author_id in author_ids:
            recent_ids = db.execute(
                select(Review.id)
                .where(
                    Review.author_id == author_id,
                    Review.published_at.isnot(None),
                    Review.published_at >= cutoff,
                    Review.is_removed.is_(False),
                )
                .order_by(Review.published_at.desc())
                .limit(RELATIONSHIP_WINDOW)
            ).scalars().all()
            if not recent_ids:
                continue
            eligible = len(recent_ids)
            tally = db.execute(
                select(ReviewVote.voter_id, func.count().label("voted"))
                .where(
                    ReviewVote.review_id.in_(recent_ids),
                    ReviewVote.created_at >= cutoff,
                )
                .group_by(ReviewVote.voter_id)
            ).all()
            for voter_id, voted in tally:
                writer.writerow([
                    str(author_id),
                    str(voter_id),
                    int(voted),
                    eligible,
                    round(wilson_lower_bound(float(voted), float(eligible)), 4),
                ])
                rows_written += 1
    return ExportResult(rows_written=rows_written, output_path=output_path)


GEO_SUMMARY_HEADER = ["country", "region", "city", "first_votes", "requests"]


def export_geo_summary(
    db: Session, output_path: str, *, since_days: int, now: datetime | None = None
) -> ExportResult:
    """Identity-free geography only: first-time votes next to traffic, by
    place and window, from the two aggregate bucket tables. No voter, no
    reader, no IP — both source tables already carry neither (design §6.2,
    §6.3)."""
    cutoff = _cutoff(since_days, now)
    vote_rows = db.execute(
        select(
            ReviewFirstVoteGeoBucket.country,
            ReviewFirstVoteGeoBucket.region,
            ReviewFirstVoteGeoBucket.city,
            func.sum(ReviewFirstVoteGeoBucket.first_vote_count).label("first_votes"),
        )
        .where(ReviewFirstVoteGeoBucket.bucket_start >= cutoff)
        .group_by(
            ReviewFirstVoteGeoBucket.country,
            ReviewFirstVoteGeoBucket.region,
            ReviewFirstVoteGeoBucket.city,
        )
    ).all()
    traffic_rows = db.execute(
        select(
            RequestGeoBucket.country,
            RequestGeoBucket.region,
            RequestGeoBucket.city,
            func.sum(RequestGeoBucket.request_count).label("requests"),
        )
        .where(RequestGeoBucket.bucket_start >= cutoff)
        .group_by(RequestGeoBucket.country, RequestGeoBucket.region, RequestGeoBucket.city)
    ).all()

    vote_map = {(r.country, r.region, r.city): int(r.first_votes) for r in vote_rows}
    traffic_map = {(r.country, r.region, r.city): int(r.requests) for r in traffic_rows}
    places = sorted(
        set(vote_map) | set(traffic_map),
        key=lambda p: (p[0] or "", p[1] or "", p[2] or ""),
    )

    rows_written = 0
    with _open_output(output_path) as handle:
        writer = csv.writer(handle)
        writer.writerow(GEO_SUMMARY_HEADER)
        for place in places:
            country, region, city = place
            writer.writerow([
                country or "", region or "", city or "",
                vote_map.get(place, 0), traffic_map.get(place, 0),
            ])
            rows_written += 1
    return ExportResult(rows_written=rows_written, output_path=output_path)


EXPORTERS = {
    "readings": export_readings,
    "vote-timing": export_vote_timing,
    "relationships": export_relationships,
    "geo-summary": export_geo_summary,
}


#: Seconds to wait for the database. Short, matching check_invariants.py: this
#: tool reports or exports, and either failing fast beats hanging silently.
CONNECT_TIMEOUT_SECONDS = 5


def _probe_engine():
    from sqlalchemy import create_engine

    from app.core.config import settings
    return create_engine(
        settings.effective_database_url,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=False,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", required=True, help="Explicit local CSV path to create.")
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument(
        "--since-days", type=_since_days, default=DEFAULT_SINCE_DAYS,
        help=f"Window in days, {MIN_SINCE_DAYS}..{MAX_SINCE_DAYS} "
             f"(default {DEFAULT_SINCE_DAYS}).")
    args = ap.parse_args(argv)

    try:
        output_path = _validate_output_path(args.output)
    except OutputPathError as exc:
        print(f"[export] {exc}", file=sys.stderr)
        return 1

    from app.core.env_guard import describe_target

    print(f"[export] target: {describe_target()}")
    print("[export] read-only; writes only the CSV named by --output")

    engine = _probe_engine()
    try:
        with engine.connect() as probe:
            from sqlalchemy import text
            probe.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        print(f"[export] cannot reach the database: {type(exc).__name__}", file=sys.stderr)
        return 2

    try:
        with Session(engine) as db:
            try:
                result = EXPORTERS[args.mode](db, output_path, since_days=args.since_days)
            finally:
                # Never a commit: every mode above is SELECT-only, and this
                # makes that fact true even if a future edit gets it wrong.
                db.rollback()
    except OutputPathError as exc:
        print(f"[export] {exc}", file=sys.stderr)
        return 1

    # Counts only, never a row's contents: this line is what shows up in
    # scrollback and screenshots, so it must stay safe to paste anywhere.
    print(f"[export] wrote {result.rows_written} rows to {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
