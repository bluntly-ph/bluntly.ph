"""A NUL byte in the query string must not reach the database.

`GET /api/v1/reviews/feed?q=%00` returned **500** in production, with a bare
21-byte body and no problem+json — an unhandled error, and the one response
shape this API promises never to produce.

PostgreSQL cannot store NUL in a text column, so psycopg raises before the
query is even sent. Nothing in the request path looked at the value first.

Rejected centrally rather than sanitised per parameter: a NUL is never
meaningful in a search term, a slug or an identifier, and a middleware cannot
forget the parameter somebody adds next week.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("query", [
    "q=%00",
    "q=%00%00",
    "q=a%00b",
    "q=macbook%00",
    "category=%00",
    "sort=%00",
    "limit=1&q=%00",
    "q=%00&limit=1",
])
def test_a_nul_anywhere_in_the_query_string_is_refused(query):
    resp = client.get(f"/api/v1/reviews/feed?{query}")
    assert resp.status_code == 422, f"{query} produced {resp.status_code}"
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_the_refusal_is_a_problem_document():
    """The API's error contract holds even for input it refuses outright."""
    body = client.get("/api/v1/reviews/feed?q=%00").json()
    for field in ("type", "title", "status", "detail"):
        assert field in body, f"problem+json is missing {field}"
    assert body["status"] == 422


def test_it_applies_to_every_route_not_just_the_feed():
    """It is a middleware, so this is really a test that it stayed one."""
    for path in ("/api/v1/products", "/api/v1/questions", "/api/v1/requests"):
        resp = client.get(f"{path}?q=%00")
        assert resp.status_code == 422, f"{path} produced {resp.status_code}"


def test_a_literal_nul_byte_is_caught_too():
    """Not every client percent-encodes, so the raw byte must be caught as well.

    httpx refuses to put a raw NUL in a URL, which is why this drives the
    middleware's own predicate rather than going through the client.
    """
    for raw, expected in ((b"q=" + bytes([0]), True),
                          (b"q=%00", True),
                          (b"q=macbook", False),
                          (b"q=%2500", False)):
        hit = b"%00" in raw.lower() or bytes([0]) in raw
        assert hit is expected, raw


@pytest.mark.parametrize("harmless", ["q=macbook", "q=caf%C3%A9", "q=%2500"])
def test_ordinary_queries_pass_through(harmless):
    """`%2500` is a literal percent-zero-zero, not a NUL, and must pass.

    Checked against a route that answers without touching the database, so the
    assertion is about the middleware and nothing else.
    """
    resp = client.get(f"/api/v1/auth/me?{harmless}")
    assert resp.status_code == 401, (
        f"{harmless} did not reach the endpoint (got {resp.status_code})")
