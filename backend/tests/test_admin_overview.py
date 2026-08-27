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
    """There is no other way to learn which half broke: the platform's function
    logs are not reachable from here."""
    out = route.admin_overview(db=_Boom(ValueError("x")))
    assert out.diagnostics == ["overview: ValueError", "affiliate: ValueError"]


def test_diagnostics_carry_class_names_only():
    """Never a message, a traceback, or row data — this is a response body."""
    out = route.admin_overview(db=_Boom(ValueError("secret-value-42")))
    assert "secret-value-42" not in str(out.diagnostics)


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
    assert out.unavailable == [] and out.diagnostics == []


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
    assert body["unavailable"] == [], f"a section failed: {body['diagnostics']}"
    assert len(body["breakdown"]) == 4
    assert len(body["affiliate"]["lifecycle"]) == 4
    assert len(body["affiliate"]["settlement"]) == 4


@requires_db
def test_activity_never_advertises_receipt_views(client):
    """`receipt_view` is an audit record of a moderator opening someone's proof
    of purchase. Surfacing it in a feed would advertise private evidence access
    as routine."""
    assert svc.ModerationAction.receipt_view not in svc.FEED_ACTIONS
