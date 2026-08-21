"""FR-2: the community price panel and the product comparison tool.

FR-2 verbatim: *"Price panel from community-submitted purchase price
observations — displayed only when ≥ 3 independent observations exist;
partial-data empty states specified."* and *"Product comparison tool:
side-by-side comparison using verified review scores, seller ratings, and
community price data."*

The threshold tests are the point of this file. "Independent" is read as
distinct submitters rather than distinct rows, because otherwise one person
posting three prices unlocks the panel alone — which is the exact thing a
threshold of three is there to prevent.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.schemas.product import _ph_today
from app.services import price_service
from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _product(client, headers) -> str:
    resp = client.post("/api/v1/products", headers=headers,
                       json={"name": f"FR2 {uuid.uuid4().hex[:10]}",
                             "category": "electronics"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _observe(client, headers, product_id, price, days_ago=0, platform="shopee"):
    return client.post(f"/api/v1/products/{product_id}/prices", headers=headers, json={
        "platform": platform,
        "price": str(price),
        "observed_at": (date.today() - timedelta(days=days_ago)).isoformat(),
        "variant": None,
    })


# --------------------------------------------------------------------------
# The threshold rule, unit level (no DB)
# --------------------------------------------------------------------------

def test_threshold_is_three_per_fr2():
    assert price_service.MIN_INDEPENDENT_OBSERVATIONS == 3


def test_median_is_used_not_mean():
    """A single absurd entry must not move the headline number much.

    Prices across platforms and variants are a skewed sample; the mean is
    deliberately not offered so nobody builds a "market price" claim on it.
    """
    assert price_service._median([Decimal("100"), Decimal("110"), Decimal("100000")]) \
        == Decimal("110")
    assert price_service._median([Decimal("100"), Decimal("200")]) == Decimal("150")


# --------------------------------------------------------------------------
# Panel behaviour
# --------------------------------------------------------------------------

@requires_db
def test_panel_hidden_until_three_independent_submitters(client):
    _, token_a, _ = register_and_token(client)
    _, token_b, _ = register_and_token(client)
    _, token_c, _ = register_and_token(client)
    a, b, c = _auth(token_a), _auth(token_b), _auth(token_c)
    product_id = _product(client, a)

    def panel():
        resp = client.get(f"/api/v1/products/{product_id}/prices")
        assert resp.status_code == 200, resp.text
        return resp.json()

    # Nothing yet: an insufficient panel, not a 404, and no prices on the wire.
    empty = panel()
    assert empty["sufficient"] is False
    assert empty["observation_count"] == 0
    assert empty["required_independent"] == 3
    assert empty["low"] is None and empty["median"] is None

    # ONE person, THREE observations -> still insufficient. This is the case
    # that a naive row count would wrongly unlock.
    for price in (1000, 1100, 1200):
        assert _observe(client, a, product_id, price).status_code == 201
    one_person = panel()
    assert one_person["observation_count"] == 3
    assert one_person["independent_count"] == 1
    assert one_person["sufficient"] is False, "one submitter is not three independent ones"
    assert one_person["low"] is None, "no prices may be published below the threshold"

    # A second independent submitter: still short.
    assert _observe(client, b, product_id, 1300).status_code == 201
    assert panel()["sufficient"] is False

    # The third unlocks it.
    assert _observe(client, c, product_id, 1500).status_code == 201
    full = panel()
    assert full["sufficient"] is True
    assert full["independent_count"] == 3
    assert full["observation_count"] == 5
    assert Decimal(full["low"]) == Decimal("1000")
    assert Decimal(full["high"]) == Decimal("1500")
    assert Decimal(full["median"]) == Decimal("1200")
    assert full["currency"] == "PHP"
    assert full["latest_observed_at"] is not None
    assert "shopee" in full["platforms"]


@requires_db
def test_submitting_a_price_requires_authentication(client):
    _, token, _ = register_and_token(client)
    product_id = _product(client, _auth(token))
    anon = client.post(f"/api/v1/products/{product_id}/prices", json={
        "platform": "shopee", "price": "999",
        "observed_at": date.today().isoformat(), "variant": None})
    assert anon.status_code == 401


@requires_db
def test_panel_is_public(client):
    _, token, _ = register_and_token(client)
    product_id = _product(client, _auth(token))
    assert client.get(f"/api/v1/products/{product_id}/prices").status_code == 200


@requires_db
def test_unknown_product_panel_is_404(client):
    assert client.get(f"/api/v1/products/{uuid.uuid4()}/prices").status_code == 404


@pytest.mark.parametrize("bad", [
    {"price": "0"},                                    # must be > 0
    {"price": "-5"},
    # Tomorrow in MANILA, not in UTC. The validator checks against the
    # Philippine date on purpose — `date.today()` is UTC on Vercel, and for the
    # eight hours where Manila is already the next day, UTC's "tomorrow" is
    # Manila's today and is legitimately accepted. Using UTC here made this
    # case fail on a CI runner at 18:47 UTC while the product was behaving
    # exactly as specified.
    {"observed_at": (_ph_today() + timedelta(days=1)).isoformat()},  # future
])
@requires_db
def test_invalid_observations_are_rejected(client, bad):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product_id = _product(client, headers)
    body = {"platform": "shopee", "price": "500",
            "observed_at": date.today().isoformat(), "variant": None}
    body.update(bad)
    assert client.post(f"/api/v1/products/{product_id}/prices",
                       headers=headers, json=body).status_code == 422


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

@requires_db
def test_compare_two_products_side_by_side(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    first, second = _product(client, headers), _product(client, headers)

    resp = client.get(f"/api/v1/products/compare?ids={first},{second}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["entries"]) == 2
    assert body["not_found"] == []
    entry = body["entries"][0]
    # Every comparable field FR-2 names, minus seller ratings (withdrawn).
    for field in ("product", "price", "review_count", "avg_rating",
                  "trust_score", "verified_review_count"):
        assert field in entry
    assert entry["price"]["sufficient"] is False, "no price data yet"


@requires_db
def test_compare_is_public(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    a, b = _product(client, headers), _product(client, headers)
    assert client.get(f"/api/v1/products/compare?ids={a},{b}").status_code == 200


@requires_db
def test_compare_rejects_too_few_and_too_many(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    ids = [_product(client, headers) for _ in range(5)]
    assert client.get(f"/api/v1/products/compare?ids={ids[0]}").status_code == 422
    assert client.get("/api/v1/products/compare?ids=").status_code == 422
    assert client.get(f"/api/v1/products/compare?ids={','.join(ids)}").status_code == 422


@requires_db
def test_compare_reports_missing_products_without_losing_the_rest(client):
    """A shared comparison link outliving one product must not 404 entirely."""
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    real_a, real_b = _product(client, headers), _product(client, headers)
    ghost = uuid.uuid4()

    resp = client.get(f"/api/v1/products/compare?ids={real_a},{real_b},{ghost}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) == 2
    assert body["not_found"] == [str(ghost)]


@requires_db
def test_compare_rejects_non_uuid_ids(client):
    assert client.get("/api/v1/products/compare?ids=not-a-uuid,also-bad").status_code == 422


@requires_db
def test_compare_carries_price_data_once_the_threshold_is_met(client):
    _, t1, _ = register_and_token(client)
    _, t2, _ = register_and_token(client)
    _, t3, _ = register_and_token(client)
    h1 = _auth(t1)
    first, second = _product(client, h1), _product(client, h1)
    for token in (t1, t2, t3):
        assert _observe(client, _auth(token), first, 2500).status_code == 201

    body = client.get(f"/api/v1/products/compare?ids={first},{second}").json()
    by_id = {e["product"]["id"]: e for e in body["entries"]}
    assert by_id[first]["price"]["sufficient"] is True
    assert Decimal(by_id[first]["price"]["median"]) == Decimal("2500")
    # The other product has none, and says so rather than borrowing.
    assert by_id[second]["price"]["sufficient"] is False


@requires_db
def test_comparison_never_claims_a_seller_rating(client):
    """FR-2 named seller ratings; they were withdrawn 2026-07-28.

    Rather than invent a value, the field is absent. On a platform about honest
    reviews, a fabricated rating would be the worst possible shortcut.
    """
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    a, b = _product(client, headers), _product(client, headers)
    body = client.get(f"/api/v1/products/compare?ids={a},{b}").json()
    blob = str(body).lower()
    assert "seller_rating" not in blob
    assert "seller_trust" not in blob


def test_compare_route_is_declared_before_the_product_id_route():
    """Route ORDER regression - genuinely no database.

    `/compare` and `/{product_id}` both match the path "compare", and FastAPI
    resolves in declaration order. When /compare was appended to the end of the
    module the id route won, tried to parse "compare" as a UUID, and every
    comparison 422'd in production while passing every DB-backed test - those
    build their URLs from real ids, so they exercise the query string rather
    than the path collision.

    An earlier version of this test issued a real request and claimed to need
    no database. It did: /compare queries products, so it failed for anyone
    without Postgres. Asserting on the route table tests the thing that
    actually broke and runs anywhere.
    """
    from app.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    compare_at = paths.index("/api/v1/products/compare")
    by_id_at = paths.index("/api/v1/products/{product_id}")
    assert compare_at < by_id_at, (
        "/products/compare must be declared before /products/{product_id}; "
        f"found compare at {compare_at}, id route at {by_id_at}"
    )
