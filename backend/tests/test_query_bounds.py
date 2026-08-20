"""Every list endpoint must bound what a caller can ask for.

`GET /api/v1/reviews/feed?limit=-1` returned **500** in production. Postgres
refuses a negative LIMIT, and the parameter was declared as a bare `int` with a
default, so nothing rejected it before it reached the query.

The unbounded upper end is the more interesting half. `limit=99999` answered
200. It looks harmless while the database holds six published reviews, and it
is not harmless: an unbounded limit on the public feed hands the entire review
corpus over in one request, which is precisely what the project's anti-scraping
mandate exists to prevent. The mandate was being enforced everywhere except in
the query string.

Some endpoints already had `Query(50, ge=1, le=100)`. The rule existed; it was
applied to about half the list endpoints and not the rest, which is the same
shape as the `javascript:` guard and the category vocabulary — a correct
decision made once and not made general.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.main import app

# Route parameters that must carry bounds, and the bound each one needs.
BOUNDED = {
    "limit": ("ge", "le"),   # a floor and a ceiling
    "offset": ("ge",),       # a floor; the ceiling is the row count
}


def _constraint(info, kind: str):
    """Read a `ge`/`le` bound off a FieldInfo.

    Pydantic keeps these in `metadata` as annotated-types markers rather than
    as attributes, so `info.le` is an AttributeError, not None - which would
    make a naive check pass by raising instead of failing.
    """
    for marker in getattr(info, "metadata", []) or []:
        value = getattr(marker, kind, None)
        if value is not None:
            return value
    return None


def _query_params():
    """(route, param name, field info) for every query parameter in the app."""
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for param in route.dependant.query_params:
            yield route, param.name, param.field_info


@pytest.mark.parametrize("name", sorted(BOUNDED))
def test_no_list_endpoint_leaves_it_unbounded(name):
    missing = []
    for route, param_name, info in _query_params():
        if param_name != name:
            continue
        for attr in BOUNDED[name]:
            if _constraint(info, attr) is None:
                missing.append(f"{route.path} ({','.join(route.methods)}) "
                               f"{param_name} has no {attr}")
    assert not missing, (
        "unbounded pagination parameters:\n  " + "\n  ".join(missing) +
        "\nUse Query(default, ge=1, le=100) — a negative value is a 500 and an "
        "unbounded one is a bulk export.")


def test_the_public_feed_cannot_be_asked_for_everything():
    """The anti-scraping mandate, as an assertion rather than a policy."""
    feed = [r for r in app.routes
            if isinstance(r, APIRoute) and r.path.endswith("/reviews/feed")]
    assert feed, "the feed route moved; this test needs updating"
    for route in feed:
        limit = next(p for p in route.dependant.query_params if p.name == "limit")
        ceiling = _constraint(limit.field_info, "le")
        assert ceiling is not None and ceiling <= 100, (
            f"the public feed allows limit={ceiling}; that is a bulk export of "
            f"the review corpus in one request")


def test_a_negative_limit_is_refused_not_executed():
    """The actual 500, pinned. Needs no database: 422 happens before the query."""
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)
    for bad in ("-1", "0", "99999", "abc"):
        resp = client.get(f"/api/v1/reviews/feed?limit={bad}")
        assert resp.status_code == 422, (
            f"limit={bad} returned {resp.status_code}; it must be refused at "
            f"validation, before it reaches Postgres")
