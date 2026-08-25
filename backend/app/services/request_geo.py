"""Vercel edge geography headers -> one canonical, non-identifying location.

This is the adapter boundary for traffic analytics. Everything downstream
speaks `RequestGeo` and never reads a raw header.

WHY THESE HEADERS. The platform already resolves visitor geography at the edge
and hands it to the function as request headers. That is first-party, costs
nothing, and needs no GeoIP vendor and no IP handling of our own. Vercel Web
Analytics was evaluated first and is not enabled for this project; there is no
historical per-request geography to backfill from, so collection starts from
the moment this ships and the UI says so rather than inventing a past.

PRIVACY. There is deliberately no IP address in this module — not as a field,
not as an input, not in a log line. The edge has already done the derivation,
so the raw address never needs to enter the application at all. What is kept is
coarse enough to be aggregate analytics rather than user tracking: country,
region, city, approximate coordinates the edge itself supplies, and the POP
that served the request.

A NOTE ON THE POP. `x-vercel-id` carries the Vercel point of presence (`sin1`,
`hnd1`). That is where the request was SERVED, not where the visitor is. The
two often disagree — a visitor in Manila is normally served from Singapore.
They are kept as separate fields for exactly that reason and must never be
presented as interchangeable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import unquote

# Vercel's edge geography headers.
H_COUNTRY = "x-vercel-ip-country"
H_REGION = "x-vercel-ip-country-region"
H_CITY = "x-vercel-ip-city"
H_LAT = "x-vercel-ip-latitude"
H_LON = "x-vercel-ip-longitude"
H_ID = "x-vercel-id"

#: Every header this module reads. Exposed so the diagnostic route can report
#: presence without hardcoding the list a second time.
GEO_HEADERS = (H_COUNTRY, H_REGION, H_CITY, H_LAT, H_LON, H_ID)

#: Values that mean "the edge could not resolve this".
_ABSENT = {"", "-", "null", "none", "undefined", "xx", "zz", "t1"}


def _clean(value: object) -> str | None:
    """A header value, or None when it is absent or a placeholder.

    `XX`/`ZZ` are the reserved unknown country codes and `T1` is the Tor exit
    pseudo-country; all three mean "not resolved" rather than a real place, and
    treating them as one would put a country called XX at the top of the chart.
    """
    text = str(value or "").strip()
    if not text or text.lower() in _ABSENT:
        return None
    return text


def _coord(value: object) -> float | None:
    """A latitude/longitude header as a float, or None. Never raises.

    Out-of-range values are dropped rather than clamped: a clamped coordinate
    is a fabricated location, and this module's whole contract is that it does
    not invent geography.
    """
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if -180.0 <= number <= 180.0 else None


def _pop(vercel_id: object) -> str | None:
    """The serving POP from `x-vercel-id`.

    The header looks like `sin1::sin1::8f2z5-1787674251475-5426d544f1a4` and
    sometimes `iad1::hnd1::...` when a request is proxied between regions. The
    FIRST segment is the POP that received the request, which is the one that
    describes where traffic arrived.
    """
    text = _clean(vercel_id)
    if text is None:
        return None
    head = text.split("::", 1)[0].strip().lower()
    # A POP code is short and alphanumeric (`sin1`, `hnd1`, `iad1`). Anything
    # else is an id shape we do not recognise, and guessing would put noise in
    # a dimension operators read as infrastructure.
    if not head or len(head) > 8 or not head.isalnum():
        return None
    return head


@dataclass(frozen=True)
class RequestGeo:
    """One request's location, at the coarsest level the edge could resolve."""

    country: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    #: Vercel POP that served the request. Infrastructure, not the visitor.
    pop: str | None = None

    @property
    def location_key(self) -> str:
        """Stable grouping key, coarsest-first so partial data still groups.

        Requests that resolved only to a country must all collapse to the same
        bucket rather than each becoming its own row, or the ranked list fills
        with near-duplicate entries that differ by nothing a reader can see.
        """
        return "|".join((self.country or "??", self.region or "", self.city or ""))

    @property
    def has_location(self) -> bool:
        """True when there is a visitor location worth recording.

        The POP alone does not count: it says where our own infrastructure is,
        and a chart built from it would show Singapore for the whole world.
        """
        return self.country is not None


def from_headers(headers: Mapping[str, str]) -> RequestGeo:
    """Normalise the edge's headers. Missing headers give an empty RequestGeo.

    Header lookup is case-insensitive because the two servers that call this
    (Starlette and the proxy) disagree about header casing, and a case-sensitive
    miss would silently produce "no geography anywhere" — which is
    indistinguishable from genuinely absent data.
    """
    lower = {str(k).lower(): v for k, v in headers.items()}

    country = _clean(lower.get(H_COUNTRY))
    return RequestGeo(
        country=country.upper() if country else None,
        region=_clean(lower.get(H_REGION)),
        # Vercel percent-encodes city names, so `Ho%20Chi%20Minh` arrives
        # literally and would otherwise be ranked as its own separate city.
        city=(lambda c: unquote(c) if c else None)(_clean(lower.get(H_CITY))),
        latitude=_coord(lower.get(H_LAT)),
        longitude=_coord(lower.get(H_LON)),
        pop=_pop(lower.get(H_ID)),
    )
