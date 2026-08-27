"""Operational traffic analytics for moderators. RBAC=moderator.

Aggregate request geography — how much traffic arrived, and roughly from where.
This is infrastructure analytics, not user analytics: nothing here can be
narrowed to a person, and no endpoint in this module returns an IP address, an
email, a user id, or a session.

`moderator` is the administrative role in this codebase (see enums.UserRole);
there is no separate `admin` role and one is not invented here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import require_role
from app.db.session import get_db
from app.services import admin_overview_service, request_traffic_service
from app.services.request_geo import GEO_HEADERS, from_headers

logger = get_logger(__name__)

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


class ActivityItemOut(BaseModel):
    action: str
    #: None for actions the system took rather than a person (a scheduled
    #: payout, a distribution run). The client renders those as "System".
    actor: str | None
    target_ref: str | None
    at: datetime


class BreakdownBarOut(BaseModel):
    label: str
    count: int


class AffiliateHealthOut(BaseModel):
    """Two separate axes, never summed together.

    `lifecycle` is what the marketplace says happened to the order; `settlement`
    is what our ledger did about it. A `completed` order can be `not_earned`
    (nobody to attribute it to) and a `returned` one can be `paid` (the return
    arrived after payout), so combining them would imply a progression that does
    not exist.
    """

    lifecycle: list[BreakdownBarOut]
    settlement: list[BreakdownBarOut]
    recognised_amount: str
    reversed_amount: str
    unrecovered_amount: str
    has_data: bool


class AdminOverviewOut(BaseModel):
    queue_total: int
    high_priority: int
    approved_today: int
    #: Signed, so the client never has to infer the comparison itself.
    approved_delta: int
    pending_affiliate: int
    honesty_fund_pool: str
    honesty_fund_month: date
    urgent: int
    breakdown: list[BreakdownBarOut]
    activity: list[ActivityItemOut]
    affiliate: AffiliateHealthOut
    #: Sections that could not be computed for this request, named so the UI can
    #: say which panel is missing instead of blanking the whole screen. Empty on
    #: a healthy response.
    unavailable: list[str] = []


@router.get("/overview", response_model=AdminOverviewOut,
            summary="Headline counts, queue breakdown and recent activity")
def admin_overview(db: Session = Depends(get_db)) -> AdminOverviewOut:
    """The Overview screen's figures.

    The queue count uses the same predicate as the queue list itself — a
    headline that disagrees with the list underneath it is worse than no
    headline at all.
    """
    # The headline counts and the affiliate ledger are independent questions.
    # They used to be computed inline, so an exception in either one returned a
    # bare 500 and the moderator lost the entire screen — including four counts
    # that had nothing to do with the failure.
    unavailable: list[str] = []

    try:
        o = admin_overview_service.overview(db)
    except Exception:  # noqa: BLE001 - the panel degrades, the request does not fail
        logger.exception("admin overview: headline counts failed")
        unavailable.append("overview")
        o = admin_overview_service.AdminOverview(
            queue_total=0, high_priority=0, approved_today=0, approved_delta=0,
            pending_affiliate=0, honesty_fund_pool=Decimal("0"),
            honesty_fund_month=date.today().replace(day=1),
        )

    try:
        health = admin_overview_service.affiliate_health(db)
    except Exception:  # noqa: BLE001 - same reasoning
        logger.exception("admin overview: affiliate health failed")
        unavailable.append("affiliate")
        health = admin_overview_service.AffiliateHealth()

    try:
        return _overview_payload(o, health, unavailable)
    except Exception:  # noqa: BLE001
        # Assembling the payload must not be able to blank the screen either.
        # 3a1bef4 guarded both service calls and production still returned a
        # bare 500, which proves the fault is outside them — so the assembly is
        # guarded too, and names itself the same way.
        logger.exception("admin overview: payload assembly failed")
        return AdminOverviewOut(
            queue_total=0, high_priority=0, approved_today=0, approved_delta=0,
            pending_affiliate=0, honesty_fund_pool="0",
            honesty_fund_month=date.today().replace(day=1), urgent=0,
            breakdown=[], activity=[],
            affiliate=AffiliateHealthOut(
                lifecycle=[], settlement=[], recognised_amount="0",
                reversed_amount="0", unrecovered_amount="0", has_data=False),
            unavailable=[*unavailable, "payload"],
        )


def _overview_payload(o, health, unavailable: list[str]) -> AdminOverviewOut:
    return AdminOverviewOut(
        queue_total=o.queue_total, high_priority=o.high_priority,
        approved_today=o.approved_today, approved_delta=o.approved_delta,
        pending_affiliate=o.pending_affiliate,
        honesty_fund_pool=str(o.honesty_fund_pool),
        honesty_fund_month=o.honesty_fund_month,
        urgent=o.urgent,
        breakdown=[BreakdownBarOut(label=b.label, count=b.count) for b in o.breakdown],
        activity=[
            ActivityItemOut(action=a.action, actor=a.actor,
                            target_ref=a.target_ref, at=a.at)
            for a in o.activity
        ],
        affiliate=AffiliateHealthOut(
            lifecycle=[BreakdownBarOut(label=b.label, count=b.count)
                       for b in health.lifecycle],
            settlement=[BreakdownBarOut(label=b.label, count=b.count)
                        for b in health.settlement],
            recognised_amount=str(health.recognised_amount),
            reversed_amount=str(health.reversed_amount),
            unrecovered_amount=str(health.unrecovered_amount),
            has_data=health.has_data,
        ),
        unavailable=unavailable,
    )
