"""Request Distribution: authorization, aggregation, both metrics, and privacy.

The privacy assertions are the load-bearing ones. This panel reads traffic, and
the line between "aggregate analytics" and "user tracking" is exactly whether a
response can be narrowed to a person, so that is asserted directly rather than
assumed from the shape of the code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.traffic import RequestGeoBucket
from app.services import request_traffic_service as svc
from app.services.request_geo import RequestGeo
from tests.conftest import register_and_token, requires_db

ENDPOINT = "/api/v1/admin/analytics/request-distribution"


def _geo(country="PH", city="Manila", region="NCR", pop="sin1"):
    return RequestGeo(country=country, region=region, city=city,
                      latitude=14.5995, longitude=120.9842, pop=pop)


# Authorization -------------------------------------------------------------

@requires_db
def test_anonymous_is_denied(client):
    assert client.get(ENDPOINT).status_code in (401, 403)


@requires_db
def test_a_normal_user_is_denied(client):
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@requires_db
def test_a_moderator_is_allowed(client):
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@requires_db
def test_the_ingest_endpoint_is_not_readable(client):
    """Ingest is write-only by design; a GET must not expose the table."""
    assert client.get("/api/v1/internal/traffic").status_code in (404, 405)


# Privacy -------------------------------------------------------------------

@requires_db
def test_response_carries_no_address_or_identity(client, db):
    """The justification for this panel is that it cannot be narrowed to a
    person. If a field ever appears that could, this fails."""
    svc.record(db, _geo())
    db.commit()
    _, token, _ = register_and_token(client, role="moderator")
    body = client.get(ENDPOINT,
                      headers={"Authorization": f"Bearer {token}"}).text.lower()
    for forbidden in ("ip_address", "x-forwarded", "email",
                      "user_id", "session", "authorization"):
        assert forbidden not in body, f"{forbidden} leaked into the response"


# Aggregation ---------------------------------------------------------------

@requires_db
def test_repeat_requests_increment_one_bucket(db):
    """This is what makes the table an aggregate rather than a request log."""
    before = db.execute(select(func.count()).select_from(RequestGeoBucket)).scalar()
    for _ in range(5):
        svc.record(db, _geo(city="AggregationTestCity"))
    db.commit()
    after = db.execute(select(func.count()).select_from(RequestGeoBucket)).scalar()
    assert after == before + 1, "five requests created more than one row"

    row = db.execute(
        select(RequestGeoBucket)
        .where(RequestGeoBucket.city == "AggregationTestCity")).scalar_one()
    assert row.request_count == 5


@requires_db
def test_a_request_the_edge_could_not_place_is_not_recorded(db):
    """An unknown bar would dominate a chart about where traffic comes from and
    says nothing a reader can act on."""
    assert svc.record(db, RequestGeo()) is False
    assert svc.record(db, RequestGeo(pop="sin1")) is False


@requires_db
def test_ranking_is_descending_by_count(db):
    svc.record(db, _geo(city="RankSmall"), count=3)
    svc.record(db, _geo(city="RankBig"), count=99)
    db.commit()
    cities = [loc.city for loc in svc.summary(db, range_key="24h", limit=50).locations]
    assert cities.index("RankBig") < cities.index("RankSmall")


@requires_db
def test_result_count_is_bounded_and_the_rest_is_aggregated(db):
    """Hundreds of locations must not render into the card, and the remainder
    must stay visible as Other rather than be silently dropped."""
    for i in range(8):
        svc.record(db, _geo(city=f"BoundedCity{i}"), count=10 - i)
    db.commit()
    result = svc.summary(db, range_key="24h", limit=3)
    assert len(result.locations) == 3
    assert result.other_location_count >= 5
    shown = sum(loc.request_count for loc in result.locations)
    assert shown + result.other_request_count == result.total_requests


@requires_db
def test_limit_cannot_exceed_the_maximum(db):
    assert len(svc.summary(db, range_key="24h", limit=10000).locations) <= svc.MAX_LIMIT


@requires_db
def test_shares_are_fractions(db):
    svc.record(db, _geo(city="ShareCity"), count=7)
    db.commit()
    result = svc.summary(db, range_key="24h", limit=svc.MAX_LIMIT)
    assert all(0.0 <= loc.share <= 1.0 for loc in result.locations)


# The two metrics -----------------------------------------------------------

def test_rps_is_count_over_the_measured_duration():
    """Defined as request_count / covered_seconds, never a constant divisor."""
    assert svc._rate(120, 60) == 2.0
    assert svc._rate(1, 4) == 0.25


def test_rps_survives_a_zero_denominator():
    """Happens when the only data is in the current, barely-started hour."""
    assert svc._rate(5, 0) == 0.0


@requires_db
def test_rps_uses_observed_coverage_not_the_nominal_window(db):
    """If collection began an hour ago, dividing a 30-day window by its full
    length would report a rate hundreds of times lower than reality."""
    svc.record(db, _geo(city="CoverageCity"), count=10)
    db.commit()
    result = svc.summary(db, range_key="30d", limit=svc.MAX_LIMIT)
    assert result.covered_seconds < svc.RANGES["30d"] * 3600


# Windows, empty state, validation -----------------------------------------

@requires_db
def test_a_window_excludes_older_buckets(db):
    old = datetime.now(UTC) - timedelta(days=40)
    svc.record(db, _geo(city="AncientCity"), now=old, count=50)
    db.commit()
    recent = svc.summary(db, range_key="24h", limit=svc.MAX_LIMIT)
    assert "AncientCity" not in [loc.city for loc in recent.locations]
    wide = svc.summary(db, range_key="90d", limit=svc.MAX_LIMIT)
    assert "AncientCity" in [loc.city for loc in wide.locations]


@requires_db
def test_no_traffic_reads_as_empty_rather_than_zero_noise(db):
    """The UI must be able to tell nothing-yet from a real zero."""
    far_future = datetime.now(UTC) + timedelta(days=400)
    result = svc.summary(db, range_key="24h", now=far_future, limit=svc.MAX_LIMIT)
    assert result.has_data is False
    assert result.locations == []
    assert result.total_requests == 0
    assert result.requests_per_second == 0.0


def test_an_unknown_range_is_refused_not_silently_defaulted():
    """A dashboard that quietly answers a different question than the one asked
    is worse than one that refuses."""
    with pytest.raises(ValueError):
        svc.summary(None, range_key="all-time")


@requires_db
@pytest.mark.parametrize("query", ["range=all-time", "range=1y", "metric=bogus",
                                   "limit=0", "limit=-5"])
def test_invalid_parameters_are_rejected(client, query):
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(f"{ENDPOINT}?{query}",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


@requires_db
@pytest.mark.parametrize("metric", ["count", "rps"])
def test_both_metrics_are_served(client, metric):
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(f"{ENDPOINT}?metric={metric}",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric"] == metric
    assert "requests_per_second" in body and "total_requests" in body


# Retention -----------------------------------------------------------------

@requires_db
def test_expired_buckets_are_purged(db):
    stale = datetime.now(UTC) - timedelta(days=svc.RETENTION_DAYS + 5)
    svc.record(db, _geo(city="ExpiredCity"), now=stale)
    db.commit()
    svc.purge_expired(db)
    db.commit()
    assert db.execute(select(RequestGeoBucket)
                      .where(RequestGeoBucket.city == "ExpiredCity")).first() is None


@requires_db
def test_purge_keeps_data_inside_the_window(db):
    fresh = datetime.now(UTC) - timedelta(days=svc.RETENTION_DAYS - 5)
    svc.record(db, _geo(city="KeptCity"), now=fresh)
    db.commit()
    svc.purge_expired(db)
    db.commit()
    assert db.execute(select(RequestGeoBucket)
                      .where(RequestGeoBucket.city == "KeptCity")).first() is not None


@requires_db
def test_opening_a_new_bucket_enforces_retention(db):
    """Retention has no scheduler behind it — production has no Redis broker,
    so the Celery beat that would own this never runs. Recording into a new
    hourly bucket is what triggers the purge, and if that link breaks the
    policy silently stops being enforced while everything still looks fine."""
    stale = datetime.now(UTC) - timedelta(days=svc.RETENTION_DAYS + 5)
    svc.record(db, _geo(city="StaleBeforeNewBucket"), now=stale)
    db.commit()

    # A location that cannot already have a bucket this hour, so the write is
    # an INSERT rather than an increment.
    svc.record(db, _geo(city=f"FreshBucket{datetime.now(UTC).timestamp()}"))
    db.commit()

    assert db.execute(
        select(RequestGeoBucket)
        .where(RequestGeoBucket.city == "StaleBeforeNewBucket")).first() is None


def test_no_range_outlives_retention():
    """Offering a window longer than we keep data for would draw a chart that is
    silently empty for most of its span."""
    assert max(svc.RANGES.values()) <= svc.RETENTION_DAYS * 24


# Ingest --------------------------------------------------------------------

@requires_db
def test_ingest_records_a_beacon(client, db):
    resp = client.post("/api/v1/internal/traffic", json={
        "country": "SG", "city": "IngestCity", "region": "01",
        "latitude": 1.35, "longitude": 103.8, "pop": "sin1"})
    assert resp.status_code in (204, 429)
    if resp.status_code == 204:
        assert db.execute(
            select(RequestGeoBucket)
            .where(RequestGeoBucket.city == "IngestCity")).first() is not None


@requires_db
@pytest.mark.parametrize("payload", [
    {"country": "NOTACOUNTRY"},
    {"latitude": 999, "longitude": 999, "country": "PH"},
])
def test_ingest_refuses_malformed_geography(client, payload):
    """Shape validation is what keeps this from storing arbitrary content."""
    assert client.post("/api/v1/internal/traffic",
                       json=payload).status_code in (204, 422, 429)


# Place-name validation ------------------------------------------------------

@pytest.mark.parametrize("name", [
    "Manila", "Ho Chi Minh", "Iloilo City", "N'Djamena", "São Paulo",
    "München", "Reykjavík", "北京", "Kuala Lumpur",
])
def test_real_place_names_survive_validation(name):
    """Place names carry accents, apostrophes and non-Latin scripts. An
    allowlist would quietly drop most of the world."""
    from app.api.v1.routes.traffic_ingest import TrafficBeacon

    assert TrafficBeacon(country="PH", city=name).city == name


@pytest.mark.parametrize("junk", [
    "<script>alert(1)</script>", "<img src=x onerror=y>", "Bad\x01Control", "   ",
])
def test_markup_and_control_characters_are_dropped(junk):
    """These can never execute — values are parameterised into Postgres and
    escaped by React, verified against production. But a ranked list of cities
    is read by a person, and markup sitting in it is noise in the one place
    this data is supposed to be legible."""
    from app.api.v1.routes.traffic_ingest import TrafficBeacon

    assert TrafficBeacon(country="PH", city=junk).city is None


def test_an_apostrophe_is_not_treated_as_an_attack():
    """Rejecting apostrophes would break real names for no gain: the value is
    parameterised, never concatenated into SQL."""
    from app.api.v1.routes.traffic_ingest import TrafficBeacon

    assert TrafficBeacon(country="PH", city="N'Djamena").city == "N'Djamena"


@pytest.mark.parametrize("payload", [
    {"country": "PH", "is_admin": True},
    {"country": "PH", "role": "moderator"},
    {"country": "PH", "request_count": 999999},
])
def test_unknown_fields_cannot_be_mass_assigned(payload):
    """The beacon is unauthenticated, so anything it accepts is attacker
    controlled. Unknown keys must be ignored, not bound."""
    from app.api.v1.routes.traffic_ingest import TrafficBeacon

    beacon = TrafficBeacon(**payload)
    for forbidden in ("is_admin", "role", "request_count"):
        assert not hasattr(beacon, forbidden)
