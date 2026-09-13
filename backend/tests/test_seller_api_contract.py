"""The seller API's shape and its guards (FR-4), checked without a database.

The behaviour lives in `test_sellers_api.py` behind `requires_db`, which skips
on every machine without Postgres. The guards are what matter most and they are
visible in the route table, so they are asserted here where they always run:

* reading a seller needs no account — FR-2: browsing does not require one;
* creating a seller, rating one, and claiming one each need an account;
* only a moderator decides a claim. A seller approving their own claim is the
  failure the whole workflow exists to prevent, so the decision route must not
  be reachable by the `seller` or `user` roles.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.core.security import get_current_user
from app.main import app

SELLER_ROUTES = {
    ("POST", "/api/v1/sellers"),
    ("GET", "/api/v1/sellers"),
    ("GET", "/api/v1/sellers/{seller_id}"),
    ("POST", "/api/v1/sellers/{seller_id}/reviews"),
    ("GET", "/api/v1/sellers/{seller_id}/reviews"),
    ("POST", "/api/v1/sellers/{seller_id}/claims"),
    ("GET", "/api/v1/admin/seller-claims"),
    ("POST", "/api/v1/admin/seller-claims/{claim_id}/decision"),
    ("POST", "/api/v1/admin/seller-reviews/{review_id}/removal"),
}


def _routes() -> dict[tuple[str, str], APIRoute]:
    table: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                table[(method, route.path)] = route
    return table


def _dependency_calls(route: APIRoute) -> list:
    """Every callable in the route's dependency tree, router-level ones included."""
    calls: list = []

    def walk(dependant) -> None:
        for sub in dependant.dependencies:
            calls.append(sub.call)
            walk(sub)

    walk(route.dependant)
    return calls


def _required_roles(route: APIRoute) -> set[str]:
    """Roles named by any `require_role(...)` guard on the route."""
    roles: set[str] = set()
    for call in _dependency_calls(route):
        for cell in getattr(call, "__closure__", None) or ():
            value = cell.cell_contents
            if isinstance(value, tuple) and value and all(isinstance(v, str) for v in value):
                roles.update(value)
    return roles


def _needs_account(route: APIRoute) -> bool:
    return get_current_user in _dependency_calls(route)


def test_every_seller_route_exists():
    missing = sorted(SELLER_ROUTES - set(_routes()))
    assert missing == [], f"missing seller routes: {missing}"


def test_reading_a_seller_needs_no_account():
    routes = _routes()
    for key in [("GET", "/api/v1/sellers"), ("GET", "/api/v1/sellers/{seller_id}"),
                ("GET", "/api/v1/sellers/{seller_id}/reviews")]:
        assert not _needs_account(routes[key]), f"{key} should be public"


def test_writing_needs_an_account():
    routes = _routes()
    for key in [("POST", "/api/v1/sellers"),
                ("POST", "/api/v1/sellers/{seller_id}/reviews"),
                ("POST", "/api/v1/sellers/{seller_id}/claims")]:
        assert _needs_account(routes[key]), f"{key} must require an account"


def test_only_moderators_see_and_decide_claims():
    routes = _routes()
    for key in [("GET", "/api/v1/admin/seller-claims"),
                ("POST", "/api/v1/admin/seller-claims/{claim_id}/decision")]:
        roles = _required_roles(routes[key])
        assert "moderator" in roles, f"{key} is not moderator-guarded: {roles}"
        assert "seller" not in roles, f"{key} lets a seller decide their own claim"
        assert "user" not in roles, f"{key} lets any user decide a claim"


def test_only_moderators_remove_a_seller_review():
    # Seller reviews publish without the product-review gate (DEVIATIONS §37),
    # so removal after the fact is the moderation hook. A store owner able to
    # remove the ratings of their own store would make the summary meaningless.
    route = _routes()[("POST", "/api/v1/admin/seller-reviews/{review_id}/removal")]
    roles = _required_roles(route)
    assert "moderator" in roles, f"removal is not moderator-guarded: {roles}"
    assert "seller" not in roles
    assert "user" not in roles
