"""The admin Overview (frame 5017:1738).

This endpoint had no tests at all, which is how it reached production returning
a bare 500 while 905 other tests stayed green. The moderation console's whole
top half — four headline counts, the activity feed and the queue breakdown —
was replaced by "Unable to load the overview right now."

The pure tests below need no database, so they run everywhere.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.api.v1.routes import admin_analytics as route
from app.services import admin_overview_service as svc
from tests.conftest import register_and_token, requires_db

ENDPOINT = "/api/v1/admin/analytics/overview"


class _Boom:
    """A session where every query raises."""

    def __init__(self, exc=LookupError("simulated")):
        self._exc = exc

    def scalars(self, *a, **k):
        raise self._exc

    def scalar(self, *a, **k):
        raise self._exc

    def execute(self, *a, **k):
        raise self._exc


# Degradation ---------------------------------------------------------------

def test_a_failing_query_does_not_take_the_whole_screen_down():
    """The four headline counts have nothing to do with the affiliate ledger.
    One failing must not blank the other."""
    out = route.admin_overview(db=_Boom())
    assert out.unavailable == ["overview", "affiliate"]
    assert out.queue_total == 0


def test_the_failing_section_is_named():
    """`unavailable` is what the UI reads to say which panel is missing."""
    out = route.admin_overview(db=_Boom(ValueError("x")))
    assert out.unavailable == ["overview", "affiliate"]


def test_no_exception_detail_reaches_the_response():
    """The temporary exception-class diagnostic was removed once the cause was
    confirmed. Nothing about the exception may appear in a response body."""
    out = route.admin_overview(db=_Boom(ValueError("secret-value-42")))
    body = out.model_dump_json()
    assert "secret-value-42" not in body
    assert "ValueError" not in body


def test_a_healthy_response_says_nothing_is_missing():
    class Empty:
        def scalars(self, *a, **k):
            return []

        def scalar(self, *a, **k):
            return 0

        def execute(self, *a, **k):
            class R:
                def all(self_):
                    return []
            return R()

    out = route.admin_overview(db=Empty())
    assert out.unavailable == []


# The service's own rules ---------------------------------------------------

def test_the_breakdown_always_has_the_four_designed_bars():
    """Even on an empty queue the design draws four labelled bars."""
    bars = svc._breakdown(None, [], set())
    assert [b.label for b in bars] == [
        "Earn Eligible", "Flagged", "New Product", "First Submission"]
    assert all(b.count == 0 for b in bars)


def test_urgent_is_the_flagged_count_not_the_queue_size():
    o = svc.AdminOverview(
        queue_total=24, high_priority=7, approved_today=18, approved_delta=3,
        pending_affiliate=18, honesty_fund_pool=Decimal("4320"),
        honesty_fund_month=date(2026, 5, 1),
    )
    assert o.urgent == 7


@pytest.mark.parametrize("utc_moment,expected", [
    # 00:00 UTC is 08:00 Manila the same date.
    (datetime(2026, 8, 27, 0, 0, tzinfo=UTC), date(2026, 8, 27)),
    # 16:00 UTC has already turned the Manila day over.
    (datetime(2026, 8, 27, 16, 0, tzinfo=UTC), date(2026, 8, 28)),
])
def test_today_is_a_manila_day(utc_moment, expected):
    """A moderator approving at 08:00 in Manila is 00:00 UTC. A UTC "today"
    would file a whole morning's work under yesterday."""
    assert svc._manila_day(utc_moment) == expected


def test_the_affiliate_axes_are_never_summed_together():
    h = svc.AffiliateHealth()
    assert h.has_data is False
    assert h.recognised_amount == Decimal("0")


# Authorization -------------------------------------------------------------

@requires_db
def test_anonymous_is_denied(client):
    assert client.get(ENDPOINT).status_code in (401, 403)


@requires_db
def test_an_ordinary_reviewer_is_denied(client):
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@requires_db
def test_a_moderator_gets_a_real_overview(client):
    """The regression this file exists for: a 200 with every section present."""
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unavailable"] == [], "a section of the overview failed"
    assert len(body["breakdown"]) == 4
    assert len(body["affiliate"]["lifecycle"]) == 4
    assert len(body["affiliate"]["settlement"]) == 4


@requires_db
def test_activity_never_advertises_receipt_views(client):
    """`receipt_view` is an audit record of a moderator opening someone's proof
    of purchase. Surfacing it in a feed would advertise private evidence access
    as routine."""
    assert svc.ModerationAction.receipt_view not in svc.FEED_ACTIONS


# The payload-assembly guard --------------------------------------------------

class _BrokenResult:
    """A result object that raises when the payload reads it.

    3a1bef4 guarded both service calls and production still returned a bare
    500, which proved the fault was outside them.
    """

    queue_total = 0
    high_priority = 0
    approved_today = 0
    approved_delta = 0
    pending_affiliate = 0
    honesty_fund_pool = Decimal("0")
    honesty_fund_month = date(2026, 8, 1)
    urgent = 0
    breakdown: list = []

    @property
    def activity(self):
        raise RuntimeError("row-level detail that must not leak")


def test_a_failure_assembling_the_payload_still_returns_a_response(monkeypatch):
    monkeypatch.setattr(route.admin_overview_service, "overview",
                        lambda db, **k: _BrokenResult())
    monkeypatch.setattr(route.admin_overview_service, "affiliate_health",
                        lambda db: svc.AffiliateHealth())
    out = route.admin_overview(db=None)
    assert "payload" in out.unavailable
    assert "row-level detail" not in out.model_dump_json()
    assert "RuntimeError" not in out.model_dump_json()


def test_one_subsystem_failing_leaves_the_other_intact(monkeypatch):
    """The four headline counts have nothing to do with the affiliate ledger."""
    monkeypatch.setattr(route.admin_overview_service, "overview",
                        lambda db, **k: svc.AdminOverview(
                            queue_total=24, high_priority=7, approved_today=18,
                            approved_delta=3, pending_affiliate=18,
                            honesty_fund_pool=Decimal("4320"),
                            honesty_fund_month=date(2026, 5, 1),
                            breakdown=[svc.BreakdownBar("Earn Eligible", 7)],
                            activity=[svc.ActivityItem("publish", None, "RV1",
                                                       datetime.now(UTC))]))

    def boom(db):
        raise LookupError("x")

    monkeypatch.setattr(route.admin_overview_service, "affiliate_health", boom)
    out = route.admin_overview(db=None)
    assert out.unavailable == ["affiliate"]
    # The counts survived.
    assert (out.queue_total, out.urgent, out.approved_delta) == (24, 7, 3)
    assert out.activity[0].target_ref == "RV1"


def test_populated_activity_and_breakdown_serialise(monkeypatch):
    """Exercises the real payload path with data, not just empty collections."""
    monkeypatch.setattr(route.admin_overview_service, "overview",
                        lambda db, **k: svc.AdminOverview(
                            queue_total=2, high_priority=1, approved_today=1,
                            approved_delta=-1, pending_affiliate=0,
                            honesty_fund_pool=Decimal("12.34"),
                            honesty_fund_month=date(2026, 8, 1),
                            breakdown=[svc.BreakdownBar(x, i) for i, x in
                                       enumerate(("Earn Eligible", "Flagged",
                                                  "New Product", "First Submission"))],
                            activity=[
                                # Production's shape: a system action with no
                                # moderator and no target.
                                svc.ActivityItem("payout", None, None,
                                                 datetime.now(UTC)),
                                svc.ActivityItem("publish", "someone", "RV9",
                                                 datetime.now(UTC)),
                            ]))
    monkeypatch.setattr(route.admin_overview_service, "affiliate_health",
                        lambda db: svc.AffiliateHealth(
                            lifecycle=[svc.BreakdownBar("Pending", 3)],
                            settlement=[svc.BreakdownBar("Earned", 3)],
                            recognised_amount=Decimal("99.99")))
    out = route.admin_overview(db=None)
    assert out.unavailable == []
    assert out.honesty_fund_pool == "12.34"
    assert [a.actor for a in out.activity] == [None, "someone"]
    assert out.affiliate.recognised_amount == "99.99"


# has_earnings ---------------------------------------------------------------
#
# Lives here rather than in a dashboard file because it was found by the same
# acceptance pass: the entry dashboard drew a chart of zeroes, and the cause was
# this predicate contradicting its own docstring.

from app.services.dashboard_service import (  # noqa: E402
    DashboardSummary,
    SeriesPoint,
)


def _summary(commission: str, amounts: list[str]) -> DashboardSummary:
    return DashboardSummary(
        range_key="30d", window_start=date(2026, 8, 1), window_end=date(2026, 8, 30),
        estimated_commission=Decimal(commission), earned_in_window=Decimal("0"),
        total_views=0,
        series=[SeriesPoint(day=date(2026, 8, 1 + i), amount=Decimal(a))
                for i, a in enumerate(amounts)],
    )


def test_a_dense_series_of_zeroes_is_not_earnings():
    """The regression. The series is one point per day and is never empty, so
    testing it for existence made this always true."""
    assert _summary("0", ["0"] * 30).has_earnings is False


def test_any_money_in_the_window_counts():
    assert _summary("0", ["0"] * 29 + ["12.50"]).has_earnings is True


def test_a_commission_with_a_flat_series_still_counts():
    """Earned outside the charted window: the total is what matters."""
    assert _summary("300", ["0"] * 30).has_earnings is True


def test_no_series_at_all_is_not_earnings():
    assert _summary("0", []).has_earnings is False


# The actual root cause -------------------------------------------------------
#
# CI reproduced the production 500 against a real database:
#
#   ValidationError: 1 validation error for ActivityItemOut
#   target_ref
#     Input should be a valid string [type=string_type,
#     input_value=UUID('d86969fb-...'), input_type=UUID]
#
# `moderation_logs.target_ref` is a UUID column. The dataclass and the response
# model both say `str | None`, and Pydantic does not coerce UUID to str. The
# offending construction sits in the route's return statement, outside both
# service guards, which is why wrapping the service calls changed nothing.

import uuid as _uuid  # noqa: E402


class _Log:
    """A moderation log shaped like the database, not like a convenient test."""

    def __init__(self, target_ref):
        self.action = svc.ModerationAction.publish
        self.target_ref = target_ref
        self.created_at = datetime.now(UTC)


def test_a_uuid_target_ref_survives_the_response_model(monkeypatch):
    """The regression. A real UUID here used to raise inside the return."""
    ref = _uuid.uuid4()

    class _DB:
        def execute(self, *a, **k):
            class R:
                def all(self_):
                    return [(_Log(ref), None, None)]
            return R()

    items = svc._activity(_DB())
    assert items[0].target_ref == str(ref)
    assert isinstance(items[0].target_ref, str)

    # And through the response model, which is where it actually blew up.
    out = route.ActivityItemOut(action="publish", actor=None,
                                target_ref=items[0].target_ref,
                                at=items[0].at)
    assert out.target_ref == str(ref)


def test_a_null_target_ref_stays_none(monkeypatch):
    """Payout and honesty-fund rows carry no target."""

    class _DB:
        def execute(self, *a, **k):
            class R:
                def all(self_):
                    return [(_Log(None), None, None)]
            return R()

    assert svc._activity(_DB())[0].target_ref is None


def test_reported_ids_are_strings_so_the_flag_comparison_can_match():
    """The silent half of the same mismatch: these are compared against
    `str(review.id)`, so as UUIDs the intersection was always empty and the
    design's "urgent" pill could never leave zero."""
    ref = _uuid.uuid4()

    class _DB:
        def scalars(self, *a, **k):
            return [ref]

    found = svc._reported_review_ids(_DB())
    assert found == {str(ref)}
    assert {str(ref)} & found, "a reported review no longer matches the queue"
