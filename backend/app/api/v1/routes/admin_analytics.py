"""Operational traffic analytics for moderators. RBAC=moderator.

Aggregate request geography — how much traffic arrived, and roughly from where.
This is infrastructure analytics, not user analytics: nothing here can be
narrowed to a person, and no endpoint in this module returns an IP address, an
email, a user id, or a session.

`moderator` is the administrative role in this codebase (see enums.UserRole);
there is no separate `admin` role and one is not invented here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.services import request_traffic_service
from app.services.request_geo import GEO_HEADERS, from_headers

router = APIRouter(prefix="/admin/analytics", tags=["admin: analytics"],
                   dependencies=[Depends(require_role("moderator"))])


class GeoProbeOut(BaseModel):
    """What the edge resolved for the CALLER'S OWN request."""

    country: str | None
    region: str | None
    city: str | None
    latitude: float | None
    longitude: float | None
    pop: str | None
    location_key: str
    has_location: bool
    #: Which geography headers the platform actually supplied, names only.
    headers_present: list[str]
    #: Which it did not. Both lists are names, never values.
    headers_absent: list[str]


@router.get("/geo-probe", response_model=GeoProbeOut,
            summary="What geography does the edge see for this request?")
def geo_probe(request: Request) -> GeoProbeOut:
    """Diagnostic: the normalised geography of the caller's own request.

    This exists because the collection below is only worth building if the
    platform genuinely supplies these headers, and the honest way to find out
    is to look at a real production request rather than to assume. It stays
    afterwards as an operations tool: when the chart looks wrong, the first
    question is always "what is the edge actually sending", and this answers it
    without reading logs.

    Safe to expose to a moderator because it describes THEIR OWN request and
    contains no address — the edge has already reduced it to a place name.
    """
    geo = from_headers(request.headers)
    present = [h for h in GEO_HEADERS if request.headers.get(h)]
    return GeoProbeOut(
        country=geo.country, region=geo.region, city=geo.city,
        latitude=geo.latitude, longitude=geo.longitude, pop=geo.pop,
        location_key=geo.location_key, has_location=geo.has_location,
        headers_present=present,
        headers_absent=[h for h in GEO_HEADERS if h not in present],
    )


class LocationOut(BaseModel):
    """One ranked place. Both metrics are resolved server-side so the client
    never re-derives a rate and reaches a different number than the total."""

    country: str | None
    region: str | None
    city: str | None
    #: Serving Vercel POP. Shown as infrastructure, never as the visitor's city.
    pop: str | None
    latitude: float | None
    longitude: float | None
    request_count: int
    requests_per_second: float
    share: float


class RequestDistributionOut(BaseModel):
    window_start: datetime
    window_end: datetime
    #: The RPS denominator, in seconds. Exposed so the UI can say what the rate
    #: is actually averaged over instead of implying the full nominal window.
    covered_seconds: int
    total_requests: int
    requests_per_second: float
    locations: list[LocationOut]
    other_request_count: int
    other_location_count: int
    has_data: bool
    range: str
    metric: str
    retention_days: int


@router.get("/request-distribution", response_model=RequestDistributionOut,
            summary="Aggregate request geography, ranked")
def request_distribution(
    metric: Literal["count", "rps"] = Query(default="count"),
    range: str = Query(default=request_traffic_service.DEFAULT_RANGE),
    limit: int = Query(default=request_traffic_service.DEFAULT_LIMIT,
                       ge=1, le=request_traffic_service.MAX_LIMIT),
    db: Session = Depends(get_db),
) -> RequestDistributionOut:
    """Where requests came from over a window.

    `metric` selects which number the UI leads with; both are always returned,
    because they are the same ranking scaled by a constant and recomputing on
    toggle would cost a round trip for data already in hand.

    An unknown `range` is a 422 from the enum below rather than a silent
    fallback to 24h: a dashboard that quietly answers a different question than
    the one asked is worse than one that refuses.
    """
    if range not in request_traffic_service.RANGES:
        raise HTTPException(
            status_code=422,
            detail=f"range must be one of {sorted(request_traffic_service.RANGES)}")

    result = request_traffic_service.summary(db, range_key=range, limit=limit)
    return RequestDistributionOut(
        window_start=result.window_start, window_end=result.window_end,
        covered_seconds=result.covered_seconds,
        total_requests=result.total_requests,
        requests_per_second=result.requests_per_second,
        locations=[LocationOut(**vars(loc)) for loc in result.locations],
        other_request_count=result.other_request_count,
        other_location_count=result.other_location_count,
        has_data=result.has_data,
        range=range, metric=metric,
        retention_days=request_traffic_service.RETENTION_DAYS,
    )
