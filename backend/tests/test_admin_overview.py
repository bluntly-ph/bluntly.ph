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


class _NoRows:
    """What `Session.scalars`/`execute` return for a query that matched nothing.

    A bare `[]` is not that: `ScalarResult` is iterable AND has `.all()`, and
    the queue assessment's candidate loader calls the latter. A fake that only
    supports the half the old code used turns a contract change into a spurious
    failure — or, worse, hides a real one.
    """

    def __iter__(self):
        return iter(())

    def all(self):
        return []


def test_a_healthy_response_says_nothing_is_missing():
    class Empty:
        def scalars(self, *a, **k):
            return _NoRows()

        def scalar(self, *a, **k):
            return 0

        def execute(self, *a, **k):
            return _NoRows()

    out = route.admin_overview(db=Empty())
    assert out.unavailable == []


# The service's own rules ---------------------------------------------------

def test_the_breakdown_always_has_the_four_designed_bars():
    """Even on an empty queue the design draws four labelled bars."""
    bars = svc._breakdown(None, [], set())
    assert [b.label for b in bars] == [
        "Earn Eligible", "Flagged", "New Product", "First Submission"]
    assert all(b.count == 0 for b in bars)


def test_urgent_is_the_overdue_count_not_the_high_band():
    """"Urgent" used to be an alias of `high_priority`, so the pill could only
    ever repeat the headline beside it. Under policy v1 they answer different
    questions: High is how much attention the item deserves, overdue is how much
    of the backlog has already missed its lane's SLA."""
    o = svc.AdminOverview(
        queue_total=24, high_priority=7, approved_today=18, approved_delta=3,
        pending_affiliate=18, honesty_fund_pool=Decimal("4320"),
        honesty_fund_month=date(2026, 5, 1), approaching_sla=5, overdue_sla=2,
    )
    assert o.urgent == 2
    assert o.high_priority == 7


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
                            approaching_sla=4, overdue_sla=2,
                            breakdown=[svc.BreakdownBar("Earn Eligible", 7)],
                            activity=[svc.ActivityItem("publish", None, "RV1",
                                                       datetime.now(UTC))]))

    def boom(db):
        raise LookupError("x")

    monkeypatch.setattr(route.admin_overview_service, "affiliate_health", boom)
    out = route.admin_overview(db=None)
    assert out.unavailable == ["affiliate"]
    # The counts survived. `urgent` is the overdue figure, not `high_priority`.
    assert (out.queue_total, out.high_priority, out.approved_delta) == (24, 7, 3)
    assert (out.urgent, out.approaching_sla, out.overdue_sla) == (2, 4, 2)
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


def test_the_flagged_bar_matches_reported_targets_by_id():
    """The original defect was a type mismatch: report ids arrived as UUIDs and
    were compared against `str(review.id)`, so the intersection was always empty
    and the Flagged bar could never leave zero. Both sides of the comparison now
    come from the same canonical assessment pass, as UUIDs."""
    reported_id = _uuid.uuid4()

    bars = svc._breakdown(
        _EmptyDB(),
        [_QueueRow(reported_id), _QueueRow(_uuid.uuid4())],
        frozenset({reported_id}),
    )
    assert _bar(bars, "Flagged") == 1, "a reported review no longer matches the queue"


# The recorded coverage follow-up ---------------------------------------------
#
# `docs/RELEASE_HANDOFF.md` left this open: the three tests above prove the type
# boundary with hand-built fakes, and a fake is precisely what let the original
# defect through. Every one of them hands the dataclass a `str` because the
# annotation says `str | None`, so none of them ever exercises the UUID the
# database actually stores. These do it against real rows, through real SQL.
#
# They assert deltas rather than absolutes. `overview()` counts the whole
# database and CI runs against a shared one, so `high_priority == 1` would pass
# alone and fail in company. Nothing here commits; the `db` fixture's rollback
# takes every row created below with it.

from app.models.enums import (  # noqa: E402
    EarnEligibleStatus,
    ModerationAction,
    ModerationReason,
    ModerationTargetType,
    Verdict,
)
from tests.conftest import make_user  # noqa: E402


def _product(db, **overrides):
    from app.models.product import Product

    overrides.setdefault("canonical_name", f"Fixture {_uuid.uuid4().hex[:8]}")
    product = Product(**overrides)
    db.add(product)
    db.flush()
    return product


def _queued_review(db, *, author, product, **overrides):
    """A review `_queue_predicate` genuinely picks up: pending and unpublished."""
    from app.models.review import Review

    overrides.setdefault("title", "Fixture review")
    overrides.setdefault("discussion", "Body text for a fixture review.")
    overrides.setdefault("verdict", Verdict.it_depends)
    overrides.setdefault("star_rating", 4)
    overrides.setdefault("is_removed", False)
    overrides.setdefault("published_at", None)
    overrides.setdefault("earn_eligible_status", EarnEligibleStatus.pending)
    review = Review(product_id=product.id, author_id=author.id, **overrides)
    db.add(review)
    db.flush()
    return review


def _report(db, target_ref, *, reporter):
    """A report row carrying a real UUID, exactly as the column stores it."""
    from app.models.moderation import ModerationLog

    log = ModerationLog(
        action=ModerationAction.report,
        target_type=ModerationTargetType.review,
        target_ref=target_ref,
        reporter_id=reporter.id,
        reason=ModerationReason.spam,
    )
    db.add(log)
    db.flush()
    return log


def _flagged(ov) -> int:
    return next(b.count for b in ov.breakdown if b.label == "Flagged")


@requires_db
def test_a_reported_queued_review_is_flagged_but_not_yet_high(db):
    """The half that failed silently: with UUIDs on both sides of the
    intersection the Flagged count stayed zero however much was reported.

    Under policy v1 the same review is NOT automatically High. One spam report
    scores 20 — enough to lift it above routine work, not enough to claim a
    moderator's next hour. Reporting something is a request for attention, not
    a verdict, and a queue where any reported item outranks everything else is
    a queue anyone can reorder.
    """
    now = datetime.now(UTC)
    before = svc.overview(db, now=now)

    product = _product(db)
    review = _queued_review(db, author=make_user(db), product=product)
    _report(db, review.id, reporter=make_user(db))

    after = svc.overview(db, now=now)

    assert after.queue_total == before.queue_total + 1
    assert _flagged(after) == _flagged(before) + 1
    assert after.high_priority == before.high_priority, "reported is not High"
    assert after.urgent == before.urgent, "a fresh report is inside its SLA"


@requires_db
def test_a_report_against_an_unrelated_uuid_flags_nothing(db):
    """A report whose target matches no review must not raise the count, or the
    pill would measure report volume rather than the queue."""
    before = svc.overview(db)

    _queued_review(db, author=make_user(db), product=_product(db))
    _report(db, _uuid.uuid4(), reporter=make_user(db))

    after = svc.overview(db)

    assert after.queue_total == before.queue_total + 1, "the review still queues"
    assert after.high_priority == before.high_priority
    assert _flagged(after) == _flagged(before)


@requires_db
def test_duplicate_reports_do_not_multiply_a_flagged_review(db):
    """Three reporters, one review. The bar counts reviews, not reports."""
    before = svc.overview(db)

    review = _queued_review(db, author=make_user(db), product=_product(db))
    for _ in range(3):
        _report(db, review.id, reporter=make_user(db))

    after = svc.overview(db)

    assert _flagged(after) == _flagged(before) + 1
    # Three reports raise the score (bracket 2-3, not 3 x bracket 1) but the
    # bar counts reviews, and one review is one review.
    assert after.high_priority == before.high_priority


@requires_db
def test_a_reported_review_outside_the_queue_is_not_urgent(db):
    """Urgency is a property of what is waiting. A published review someone
    reported is moderation work, but it is not queue work."""
    before = svc.overview(db)

    published = _queued_review(
        db,
        author=make_user(db),
        product=_product(db),
        published_at=datetime.now(UTC),
        earn_eligible_status=EarnEligibleStatus.approved,
    )
    _report(db, published.id, reporter=make_user(db))

    after = svc.overview(db)

    assert after.queue_total == before.queue_total, "it is not awaiting moderation"
    assert after.high_priority == before.high_priority
    assert _flagged(after) == _flagged(before)


# The canonical priority contract ---------------------------------------------
#
# Overview used to define "high priority" as the reviews someone had reported,
# and alias "urgent" to that same number, while the queue underneath it ordered
# itself by a different rule again. Two screens, two definitions, one backlog —
# the pill could disagree with the list it sat above.
#
# Both now read ONE evaluation: `referral_service.assess_open_queue` assesses
# the whole queue against policy v1, and Overview reports its aggregates. The
# tests below pin that the headline counts ARE the assessment's counts, and
# that `Flagged` keeps its own separate meaning (reported) rather than being
# quietly reused as a synonym for the High band.

from datetime import timedelta  # noqa: E402

from app.services import referral_service  # noqa: E402
from app.services.moderation_priority import (  # noqa: E402
    PriorityBand,
    PriorityLane,
    SlaState,
)


class _EmptyDB:
    """A session that answers every query with nothing."""

    def scalars(self, *a, **k):
        return _NoRows()

    def scalar(self, *a, **k):
        return 0

    def execute(self, *a, **k):
        return _NoRows()


class _QueueRow:
    """The handful of review attributes the breakdown bars actually read."""

    def __init__(self, id):
        self.id = id
        self.verification_status = None
        self.product_id = _uuid.uuid4()
        self.author_id = _uuid.uuid4()


def _bar(bars, label: str) -> int:
    return next(b.count for b in bars if b.label == label)


def _fake_summary(**counts):
    from app.schemas.referral import QueueCounts

    return referral_service.QueueAssessmentSummary(
        reviews=(),
        counts=QueueCounts(**counts),
        reported_review_ids=frozenset(),
    )


def test_the_headline_counts_are_the_canonical_assessment_counts(monkeypatch):
    """Overview does not recount the queue. It reports what the single
    evaluation pass already decided, so the pill and the list cannot drift."""
    monkeypatch.setattr(
        referral_service,
        "assess_open_queue",
        lambda db, *, now=None: _fake_summary(
            total=9,
            by_lane={"reported": 2, "integrity": 3, "routine": 4},
            by_band={"high": 4, "normal": 3, "low": 2},
            by_sla={"overdue": 2, "approaching": 3, "on_track": 4},
        ),
    )

    o = svc.overview(_EmptyDB())

    assert o.queue_total == 9
    assert o.high_priority == 4
    assert o.approaching_sla == 3
    assert o.overdue_sla == 2
    assert o.urgent == 2, "the design's urgent pill is the overdue count"


def test_high_priority_no_longer_means_reported(monkeypatch):
    """A review reaches High by being overdue, or by scoring 40 on integrity
    factors, with nobody having reported it at all. Defining High as "somebody
    complained" made the headline a measure of report volume."""
    monkeypatch.setattr(
        referral_service,
        "assess_open_queue",
        lambda db, *, now=None: _fake_summary(
            total=3,
            by_lane={"reported": 0, "integrity": 3, "routine": 0},
            by_band={"high": 3, "normal": 0, "low": 0},
            by_sla={"overdue": 1, "approaching": 0, "on_track": 2},
        ),
    )

    o = svc.overview(_EmptyDB())

    assert o.high_priority == 3, "no report filed, still High"
    assert _flagged(o) == 0, "and Flagged still means reported"


def test_the_response_carries_both_sla_counts(monkeypatch):
    """The route must forward the SLA figures, or the console can show a
    backlog without showing that part of it is already late."""
    monkeypatch.setattr(
        referral_service,
        "assess_open_queue",
        lambda db, *, now=None: _fake_summary(
            total=5,
            by_band={"high": 1, "normal": 2, "low": 2},
            by_sla={"overdue": 1, "approaching": 2, "on_track": 2},
        ),
    )

    out = route.admin_overview(db=_EmptyDB())

    assert out.unavailable == []
    assert out.approaching_sla == 2
    assert out.overdue_sla == 1
    assert out.urgent == 1


def test_a_failed_assessment_does_not_report_zero_late_work():
    """An unavailable queue must not render as a calm, empty, on-time backlog.
    `unavailable` is what lets the UI say the panel is missing instead."""
    out = route.admin_overview(db=_Boom())

    assert "overview" in out.unavailable
    assert out.approaching_sla == 0
    assert out.overdue_sla == 0


# Against real rows -----------------------------------------------------------
#
# The fakes above prove the wiring, and a fake is exactly what let the original
# UUID/str defect through. These run the real policy over real SQL. They assert
# equality between the two screens rather than absolute numbers, because
# `overview()` counts the whole database and CI runs against a shared one.


def _vote(db, review_id, voter_id):
    from app.models.enums import VoteDirection
    from app.models.vote import ReviewVote

    vote = ReviewVote(review_id=review_id, voter_id=voter_id, vote=VoteDirection.up)
    db.add(vote)
    db.flush()
    return vote


def _distinct_review(db, *, title, body, created_at=None):
    """A queued review with its own product, author and body.

    Its own product AND author because the duplicate-content detector only
    considers candidates sharing one of the two — fixtures sharing either would
    flag each other as duplicates and move the lane under test.
    """
    overrides = {"title": title, "discussion": body}
    if created_at is not None:
        overrides["created_at"] = created_at
    return _queued_review(db, author=make_user(db), product=_product(db), **overrides)


def _full_counts(db, now):
    return referral_service.get_prioritized_queue(
        db, referral_service.QueueQuery(limit=1), now=now
    ).counts


@requires_db
def test_overview_totals_equal_the_canonical_queue_counts(db):
    """The contract in one line: what the queue says its backlog is, is what
    the Overview reports."""
    now = datetime.now(UTC)

    counts = _full_counts(db, now)
    ov = svc.overview(db, now=now)

    assert ov.queue_total == counts.total
    assert ov.high_priority == counts.by_band.get(PriorityBand.high.value, 0)
    assert ov.urgent == counts.by_sla.get(SlaState.overdue.value, 0)
    assert ov.approaching_sla == counts.by_sla.get(SlaState.approaching.value, 0)
    assert ov.overdue_sla == ov.urgent


@requires_db
def test_the_four_policy_shapes_classify_the_same_on_both_screens(db):
    """A collusion-only review, a report-only review, an overdue routine review
    and a clear on-track one. Each lands in one lane and one band, and the
    Overview's totals are those same classifications, counted."""
    now = datetime.now(UTC)
    marker = _uuid.uuid4().hex[:10]

    on_track = _distinct_review(
        db,
        title=f"{marker} on track",
        body="Bought it, used it for a fortnight, and the battery held up fine.",
        created_at=now - timedelta(minutes=5),
    )
    overdue = _distinct_review(
        db,
        title=f"{marker} overdue",
        body="Arrived dented but works; the seller replaced the lid without argument.",
        created_at=now - timedelta(hours=30),
    )
    reported = _distinct_review(
        db,
        title=f"{marker} reported",
        body="Genuinely loud under load, which nobody in the listing mentions at all.",
        created_at=now - timedelta(minutes=5),
    )
    _report(db, reported.id, reporter=make_user(db))

    colluding = _distinct_review(
        db,
        title=f"{marker} collusion",
        body="Compact, cheap, and the strap frayed within a month of daily use.",
        created_at=now - timedelta(minutes=5),
    )
    ring = [make_user(db) for _ in range(5)]
    for member in ring:
        _vote(db, colluding.id, member.id)
    # Four of the five voters get an up-vote back from the author: 4/5 = 0.8,
    # over the 0.6 reciprocation threshold. The fifth is what keeps this a
    # ratio rather than a clean sweep.
    for index, member in enumerate(ring[:4]):
        theirs = _queued_review(
            db,
            author=member,
            product=_product(db),
            title=f"ring member {index} {_uuid.uuid4().hex[:6]}",
            discussion=f"An unrelated review body, number {index}, {_uuid.uuid4().hex}.",
        )
        _vote(db, theirs.id, colluding.author_id)

    page = referral_service.get_prioritized_queue(
        db, referral_service.QueueQuery(q=marker, limit=50), now=now
    )
    seen = {item.review.id: item.priority for item in page.items}
    assert set(seen) == {on_track.id, overdue.id, reported.id, colluding.id}

    assert seen[on_track.id].lane == PriorityLane.routine
    assert seen[on_track.id].sla_state == SlaState.on_track
    assert seen[on_track.id].band == PriorityBand.low

    assert seen[overdue.id].lane == PriorityLane.routine
    assert seen[overdue.id].sla_state == SlaState.overdue
    assert seen[overdue.id].band == PriorityBand.high, "past its SLA is High"

    assert seen[reported.id].lane == PriorityLane.reported
    assert seen[reported.id].band == PriorityBand.normal
    assert "report_count_1" in {f.code for f in seen[reported.id].factors}

    assert seen[colluding.id].lane == PriorityLane.integrity
    assert seen[colluding.id].band == PriorityBand.normal
    assert "collusion" in {f.code for f in seen[colluding.id].factors}

    counts = _full_counts(db, now)
    ov = svc.overview(db, now=now)
    assert ov.high_priority == counts.by_band.get(PriorityBand.high.value, 0)
    assert ov.urgent == counts.by_sla.get(SlaState.overdue.value, 0)


@requires_db
def test_flagged_counts_reported_targets_not_the_high_band(db):
    """Two different questions, and the bar answers the one it is labelled
    with. An overdue review nobody reported is High and not Flagged; a fresh
    reported one is Flagged and not High."""
    now = datetime.now(UTC)
    before = svc.overview(db, now=now)

    _distinct_review(
        db,
        title="Late and unremarked",
        body="Perfectly ordinary purchase, nothing controversial, it just sat waiting.",
        created_at=now - timedelta(hours=30),
    )
    reported = _distinct_review(
        db,
        title="Fresh and complained about",
        body="The measurements in the listing are wrong by about two centimetres.",
        created_at=now - timedelta(minutes=1),
    )
    _report(db, reported.id, reporter=make_user(db))

    after = svc.overview(db, now=now)

    assert after.queue_total == before.queue_total + 2
    assert after.high_priority == before.high_priority + 1, "the overdue one"
    assert after.urgent == before.urgent + 1
    assert _flagged(after) == _flagged(before) + 1, "the reported one"
