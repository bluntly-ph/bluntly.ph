"""The store owner's dashboard (FR-4 "review monitoring"), checked without a database.

A claimed store's owner needs to see how their store is being rated over time
and which buyer questions are still waiting on them. The rules that decide
what the dashboard says are pinned here:

* review volume is counted per **Manila** calendar month, zero-filled, oldest
  first, for a fixed window — a month with no reviews is a zero, not a gap a
  chart would silently close;
* the dashboard and the list of the caller's stores need an account, and
  `/sellers/mine` is declared before `/sellers/{seller_id}` so "mine" is never
  parsed as a store id.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.seller_service import monthly_volume
from tests.test_seller_api_contract import _needs_account, _routes


def _review(year: int, month: int, day: int = 15) -> SimpleNamespace:
    return SimpleNamespace(created_at=datetime(year, month, day, 4, 0, tzinfo=UTC))


class TestMonthlyVolume:

    def test_months_are_zero_filled_and_oldest_first(self):
        volume = monthly_volume([_review(2026, 9), _review(2026, 9), _review(2026, 7)],
                                months=3, today=date(2026, 9, 14))
        assert volume == [
            {"month": "2026-07", "count": 1},
            {"month": "2026-08", "count": 0},
            {"month": "2026-09", "count": 2},
        ]

    def test_the_window_crosses_a_year(self):
        volume = monthly_volume([_review(2025, 12)], months=3, today=date(2026, 2, 1))
        assert volume == [
            {"month": "2025-12", "count": 1},
            {"month": "2026-01", "count": 0},
            {"month": "2026-02", "count": 0},
        ]

    def test_reviews_before_the_window_are_not_counted(self):
        volume = monthly_volume([_review(2025, 11)], months=3, today=date(2026, 2, 1))
        assert sum(m["count"] for m in volume) == 0

    def test_the_month_is_the_manila_month(self):
        # 2026-08-31 17:00 UTC is 2026-09-01 01:00 in Manila.
        late_august_utc = SimpleNamespace(created_at=datetime(2026, 8, 31, 17, 0, tzinfo=UTC))
        volume = monthly_volume([late_august_utc], months=2, today=date(2026, 9, 14))
        assert volume == [{"month": "2026-08", "count": 0}, {"month": "2026-09", "count": 1}]


def test_the_dashboard_and_my_stores_need_an_account():
    routes = _routes()
    for key in [("GET", "/api/v1/sellers/mine"),
                ("GET", "/api/v1/sellers/{seller_id}/dashboard")]:
        assert key in routes, f"missing {key}"
        assert _needs_account(routes[key]), f"{key} must require an account"


def test_mine_is_declared_before_the_store_id_route():
    from app.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    assert paths.index("/api/v1/sellers/mine") < paths.index("/api/v1/sellers/{seller_id}"), (
        "/sellers/mine must be declared before /sellers/{seller_id}, or 'mine' is "
        "parsed as a store id and every call 422s")
