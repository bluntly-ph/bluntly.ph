"""Operational traffic analytics for moderators. RBAC=moderator.

Aggregate request geography — how much traffic arrived, and roughly from where.
This is infrastructure analytics, not user analytics: nothing here can be
narrowed to a person, and no endpoint in this module returns an IP address, an
email, a user id, or a session.

`moderator` is the administrative role in this codebase (see enums.UserRole);
there is no separate `admin` role and one is not invented here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.security import require_role
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
