"""The edge-header -> location adapter.

These are the rules the traffic chart depends on. Each one exists because
getting it wrong produces a chart that looks plausible and is false, which is
worse than a chart that is obviously empty.
"""

from __future__ import annotations

import pytest

from app.services.request_geo import from_headers


def test_reads_the_normal_case():
    geo = from_headers({
        "x-vercel-ip-country": "PH",
        "x-vercel-ip-country-region": "NCR",
        "x-vercel-ip-city": "Manila",
        "x-vercel-ip-latitude": "14.5995",
        "x-vercel-ip-longitude": "120.9842",
        "x-vercel-id": "sin1::sin1::8f2z5-1787674251475-5426d544f1a4",
    })
    assert (geo.country, geo.region, geo.city) == ("PH", "NCR", "Manila")
    assert (geo.latitude, geo.longitude) == (14.5995, 120.9842)
    assert geo.pop == "sin1"
    assert geo.has_location


def test_header_lookup_is_case_insensitive():
    """Starlette and the proxy disagree about casing. A case-sensitive miss
    would read as "no geography anywhere", which is indistinguishable from
    genuinely absent data and would silently empty the chart."""
    assert from_headers({"X-Vercel-IP-Country": "SG"}).country == "SG"


def test_city_is_percent_decoded():
    """Vercel percent-encodes city names. Left encoded, `Ho%20Chi%20Minh`
    ranks as its own city separate from `Ho Chi Minh`."""
    assert from_headers({"x-vercel-ip-city": "Ho%20Chi%20Minh"}).city == "Ho Chi Minh"


@pytest.mark.parametrize("code", ["XX", "ZZ", "T1", "xx", "", "-"])
def test_unresolved_country_codes_are_not_places(code):
    """XX/ZZ are the reserved 'unknown' codes and T1 is the Tor pseudo-country.
    Treated as real, one of them tops the ranked list as a country that does
    not exist."""
    assert from_headers({"x-vercel-ip-country": code}).country is None


def test_country_is_upper_cased():
    assert from_headers({"x-vercel-ip-country": "ph"}).country == "PH"


@pytest.mark.parametrize("value", ["", "abc", "999", "-181", "181", None])
def test_bad_coordinates_are_dropped_not_clamped(value):
    """A clamped coordinate is a fabricated location."""
    geo = from_headers({"x-vercel-ip-latitude": value, "x-vercel-ip-longitude": value})
    assert geo.latitude is None and geo.longitude is None


def test_pop_takes_the_first_segment():
    """`iad1::hnd1::...` means received at iad1 and proxied on. The first
    segment is where traffic actually arrived."""
    assert from_headers({"x-vercel-id": "iad1::hnd1::abc"}).pop == "iad1"


@pytest.mark.parametrize("value", ["", "not-a-pop-code-at-all", "sin 1"])
def test_unrecognised_vercel_id_gives_no_pop(value):
    assert from_headers({"x-vercel-id": value}).pop is None


def test_pop_alone_is_not_a_visitor_location():
    """The POP says where OUR infrastructure is. A chart built from it shows
    Singapore for the entire world."""
    geo = from_headers({"x-vercel-id": "sin1::sin1::abc"})
    assert geo.pop == "sin1"
    assert not geo.has_location


def test_partial_data_groups_at_the_coarsest_level():
    """Country-only requests must collapse into one bucket, not become one
    near-duplicate row each."""
    a = from_headers({"x-vercel-ip-country": "PH"})
    b = from_headers({"x-vercel-ip-country": "PH"})
    assert a.location_key == b.location_key
    assert a.location_key != from_headers(
        {"x-vercel-ip-country": "PH", "x-vercel-ip-city": "Manila"}).location_key


def test_no_headers_at_all_is_empty_not_an_error():
    """Local development and any non-Vercel host send none of these. That must
    read as 'no data yet', never as a crash on every request."""
    geo = from_headers({})
    assert not geo.has_location
    assert geo.country is None and geo.pop is None


def test_module_never_touches_an_ip_address():
    """The edge has already done the derivation, so the raw address never needs
    to enter the application. Guarding it here keeps a future edit honest."""
    import inspect

    from app.services import request_geo

    source = inspect.getsource(request_geo).lower()
    for forbidden in ("x-forwarded-for", "x-real-ip", "request.client", "ipaddress"):
        assert forbidden not in source, f"{forbidden} must not appear in request_geo"
