"""Aggregate traffic geography: record it, rank it, and forget it on time.

Reads and writes `request_geo_buckets`. Nothing here handles an IP address or a
user id — the edge resolves location before the request arrives, so neither is
needed to answer "how much traffic, from roughly where".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.traffic import RequestGeoBucket
from app.services.request_geo import RequestGeo

#: Selectable windows, in hours. Capped by RETENTION_DAYS: offering a range
#: longer than we keep data for would draw a 1-year chart that is silently
#: empty for 275 days of it.
RANGES: dict[str, int] = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "90d": 24 * 90}
DEFAULT_RANGE = "24h"

#: How long hourly buckets are kept. Stricter than the published privacy
#: policy's general retention language, so it needs no policy change.
RETENTION_DAYS = 90

#: Ranked rows returned to the UI. The remainder is aggregated into "Other"
#: rather than dropped, so the visible bars always sum to the stated total.
DEFAULT_LIMIT = 15
MAX_LIMIT = 50


def _hour(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def record(db: Session, geo: RequestGeo, *, now: datetime | None = None,
           count: int = 1) -> bool:
    """Add one request to its (hour x location) bucket. Returns False if skipped.

    A request the edge could not place is not recorded at all. Storing it as an
    "unknown" row would put a large, permanent, uninterpretable bar in a chart
    whose entire purpose is showing where traffic comes from — and the honest
    signal (that some traffic is unresolved) is already visible as the gap
    between this total and any other request count.

    The UPSERT is what keeps this an aggregate rather than a log: concurrent
    requests from the same city in the same hour contend on one row and
    increment it.
    """
    if not geo.has_location:
        return False

    moment = now or datetime.now(UTC)
    bucket = _hour(moment)
    stmt = insert(RequestGeoBucket).values(
        bucket_start=bucket,
        country=geo.country, region=geo.region, city=geo.city, pop=geo.pop,
        latitude=geo.latitude, longitude=geo.longitude,
        request_count=count,
    )
    # Inferred from the index's columns rather than named as a constraint:
    # migration 0032 creates `uq_request_geo_bucket` with CREATE UNIQUE INDEX
    # (the only way to get NULLS NOT DISTINCT), and an index is not a
    # constraint — `ON CONFLICT ON CONSTRAINT` fails against it at runtime.
    inserted = db.execute(
        stmt.on_conflict_do_update(
            index_elements=["bucket_start", "country", "region", "city", "pop"],
            set_={
                "request_count": RequestGeoBucket.request_count + count,
                "updated_at": func.now(),
            },
            # `xmax = 0` is true only of a freshly INSERTed row, so this tells
            # a new bucket apart from an increment of an existing one.
        ).returning(text("(xmax = 0) AS inserted"))
    ).scalar()

    # Retention is enforced here rather than by a scheduler. Production has no
    # Redis broker, so the Celery beat that would otherwise own this does not
    # run — and a retention policy that nothing executes is not a policy.
    # Tying it to a NEW bucket bounds it to at most once per hour per location,
    # and the delete is an indexed range scan that normally matches nothing.
    if inserted:
        purge_expired(db, now=moment)
    return True


@dataclass(frozen=True)
class Location:
    """One ranked place, with both metrics already resolved."""

    country: str | None
    region: str | None
    city: str | None
    pop: str | None
    latitude: float | None
    longitude: float | None
    request_count: int
    requests_per_second: float
    share: float


@dataclass(frozen=True)
class TrafficSummary:
    window_start: datetime
    window_end: datetime
    #: Seconds actually covered by data — the RPS denominator. NOT the nominal
    #: window: if collection began an hour ago, dividing a 24h window by 86400
    #: would report a rate 24x lower than what is really happening.
    covered_seconds: int
    total_requests: int
    requests_per_second: float
    locations: list[Location] = field(default_factory=list)
    other_request_count: int = 0
    other_location_count: int = 0

    @property
    def has_data(self) -> bool:
        return self.total_requests > 0


def _rate(count: int, seconds: int) -> float:
    """Requests per second over an actual measured duration.

    Defined as `request_count / covered_seconds` — a mean rate, not a peak.
    Guarded against a zero denominator, which happens when the only data is in
    the current partially-elapsed hour.
    """
    return round(count / seconds, 4) if seconds > 0 else 0.0


def summary(db: Session, *, range_key: str = DEFAULT_RANGE,
            limit: int = DEFAULT_LIMIT,
            now: datetime | None = None) -> TrafficSummary:
    """Ranked geography for a window, with counts and rates.

    Ranking is always by request_count; RPS is the same ordering divided by a
    constant, so offering it as a separate sort would only look like a
    different answer to the same question.
    """
    if range_key not in RANGES:
        raise ValueError(f"unknown range: {range_key}")
    limit = max(1, min(int(limit), MAX_LIMIT))

    end = now or datetime.now(UTC)
    start = _hour(end) - timedelta(hours=RANGES[range_key] - 1)

    rows = db.execute(
        select(
            RequestGeoBucket.country, RequestGeoBucket.region,
            RequestGeoBucket.city, RequestGeoBucket.pop,
            func.max(RequestGeoBucket.latitude).label("latitude"),
            func.max(RequestGeoBucket.longitude).label("longitude"),
            func.sum(RequestGeoBucket.request_count).label("request_count"),
        )
        .where(RequestGeoBucket.bucket_start >= start)
        .group_by(RequestGeoBucket.country, RequestGeoBucket.region,
                  RequestGeoBucket.city, RequestGeoBucket.pop)
        .order_by(text("request_count DESC"))
    ).all()

    earliest = db.execute(
        select(func.min(RequestGeoBucket.bucket_start))
        .where(RequestGeoBucket.bucket_start >= start)
    ).scalar()

    total = sum(int(r.request_count) for r in rows)
    # Cover from the first bucket we actually have (never earlier than the
    # window) to now. A bucket is an hour wide and its stamp is the hour's
    # START, so a bucket that began 10 minutes ago has covered 10 minutes.
    covered = int((end - max(earliest, start)).total_seconds()) if earliest else 0

    top = rows[:limit]
    rest = rows[limit:]
    return TrafficSummary(
        window_start=start, window_end=end,
        covered_seconds=max(covered, 0),
        total_requests=total,
        requests_per_second=_rate(total, covered),
        locations=[
            Location(
                country=r.country, region=r.region, city=r.city, pop=r.pop,
                latitude=float(r.latitude) if r.latitude is not None else None,
                longitude=float(r.longitude) if r.longitude is not None else None,
                request_count=int(r.request_count),
                requests_per_second=_rate(int(r.request_count), covered),
                share=round(int(r.request_count) / total, 4) if total else 0.0,
            )
            for r in top
        ],
        other_request_count=sum(int(r.request_count) for r in rest),
        other_location_count=len(rest),
    )


def purge_expired(db: Session, *, now: datetime | None = None) -> int:
    """Drop buckets past the retention window. Returns rows removed."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    result = db.execute(
        delete(RequestGeoBucket).where(RequestGeoBucket.bucket_start < cutoff))
    return int(result.rowcount or 0)
