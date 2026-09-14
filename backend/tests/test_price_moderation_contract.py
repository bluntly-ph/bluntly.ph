"""Price observation moderation (FR-2, completion contract), without a database.

Observations were counted the moment they were posted. The contract makes them
pending, approved or rejected, with the panel built only from approved ones, a
moderator queue to decide them, and the composer's "Let's talk money" price
feeding the same pipeline. What can be checked without Postgres is checked
here; the flow itself is in `test_price_and_compare.py` behind `requires_db`.
"""

from __future__ import annotations

from app.models.enums import PriceObservationSource, PriceObservationStatus
from app.models.product import PriceHistory
from app.schemas.product import PriceObservationOut, PricePanelOut
from app.schemas.review import ReviewCreate
from tests.test_seller_api_contract import _required_roles, _routes

QUEUE = ("GET", "/api/v1/admin/price-observations")
DECISION = ("POST", "/api/v1/admin/price-observations/{observation_id}/decision")


def test_the_three_states():
    assert [s.value for s in PriceObservationStatus] == ["pending", "approved", "rejected"]


def test_an_observation_says_where_it_came_from():
    assert [s.value for s in PriceObservationSource] == ["manual", "review"]


def test_a_new_row_is_pending_in_the_database_itself():
    # server_default, so a row written by any path - including an old build
    # still running during a deploy - starts unmoderated rather than counted.
    default = PriceHistory.__table__.c.status.server_default
    assert default is not None and "pending" in str(default.arg)


def test_the_moderator_routes_exist():
    routes = _routes()
    assert QUEUE in routes
    assert DECISION in routes


def test_only_moderators_decide_prices():
    routes = _routes()
    for key in (QUEUE, DECISION):
        roles = _required_roles(routes[key])
        assert "moderator" in roles, f"{key} is not moderator-guarded: {roles}"
        assert "user" not in roles and "seller" not in roles


def test_the_panel_reports_what_is_waiting():
    assert "pending_count" in PricePanelOut.model_fields


def test_a_submitter_is_told_the_status():
    assert "status" in PriceObservationOut.model_fields


def test_a_review_may_say_where_the_price_was_paid():
    base = {"product_id": "00000000-0000-0000-0000-000000000001", "title": "t",
            "discussion": "d" * 40, "verdict": "it_depends", "star_rating": 4}
    assert ReviewCreate(**base).price_platform is None
    assert ReviewCreate(**base, price_paid="499", price_platform="lazada").price_platform.value \
        == "lazada"
