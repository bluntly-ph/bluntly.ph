"""Assertions behind every claim in docs/RANKING_SIMULATION.md.

Two halves:

1. Pure-math scenario tests. These run everywhere, no database. They assert on
   the same `sim.scenarios` output that renders the committed graphs, so a chart
   in the document cannot drift from a passing test.
2. One rollback-isolated end-to-end test proving a vote influx actually reorders
   the feed. It opens its own connection-level transaction and rolls it back, so
   it writes nothing even when pointed at the production Supabase configuration.

The findings in the document (F1: fraud signals unreachable for voted reviews,
F2: velocity detection is up-vote-only) are asserted here as *current behaviour*.
If someone fixes them, these tests fail loudly and the document must be updated
alongside — which is the point.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.services.ranking import (
    DECAY_HALF_LIFE_DAYS,
    GATE_WILSON_LB,
    VELOCITY_THRESHOLD,
    wilson_lower_bound,
)
from sim import scenarios as S
from tests.conftest import requires_db


# --------------------------------------------------------------------------
# S1 — small-n vs large-n
# --------------------------------------------------------------------------
def test_s1_wilson_ranks_more_evidence_above_a_better_raw_percentage():
    """The claim the whole ranking rests on: 95/100 outranks a perfect 5/5."""
    assert wilson_lower_bound(5, 5) < wilson_lower_bound(95, 100)


def test_s1_wilson_is_strictly_increasing_in_n_at_a_fixed_rate():
    result = S.small_n_vs_large_n()
    series = result.wilson["100% positive"]
    assert all(b > a for a, b in zip(series, series[1:], strict=False))


def test_s1_wilson_never_exceeds_the_naive_proportion():
    result = S.small_n_vs_large_n()
    for label in result.naive:
        for naive, wilson in zip(result.naive[label], result.wilson[label],
                                 strict=True):
            assert wilson <= naive


def test_s1_a_single_perfect_vote_scores_poorly():
    """One 100% review must not be able to hold a homepage slot."""
    assert wilson_lower_bound(1, 1) < 0.25


# --------------------------------------------------------------------------
# S2 — brigade burst
# --------------------------------------------------------------------------
def test_s2_brigade_overtakes_the_organic_control():
    result = S.brigade_burst()
    assert result.target_score[0] < result.control_score[0]
    assert result.target_score[-1] > result.control_score[-1]


def test_s2_brigade_reaches_the_homepage_within_the_burst_window():
    result = S.brigade_burst()
    entry = result.minute_entering_homepage
    assert entry is not None
    assert 0 <= entry <= result.burst_minutes
    assert result.target_rank[0] > S.HOMEPAGE_SLOTS
    assert result.target_rank[-1] == 1


def test_s2_velocity_signal_fires_on_the_burst_but_not_on_organic_traffic():
    result = S.brigade_burst()
    assert result.first_flag_minute is not None
    assert result.velocity_flag[-1] is True
    assert result.hourly_upvotes[-1] > VELOCITY_THRESHOLD
    # The organic control never trips it, so the signal is not merely trigger-happy.
    assert S.velocity_at(result.control_votes, 30.0) is False


# --------------------------------------------------------------------------
# S3 — decay handover
# --------------------------------------------------------------------------
def test_s3_a_frozen_champion_is_overtaken_by_a_steady_challenger():
    result = S.decay_handover()
    day = result.crossover_day
    assert day is not None
    assert 30 < day < 90, f"crossover drifted to day {day}"
    assert result.challenger_score[-1] > result.champion_score[-1]


def test_s3_champion_effective_n_follows_the_closed_form():
    """Effective n must decay as n * 0.5 ** (t / half_life) — the ADR-004 curve."""
    result = S.decay_handover()
    for day, actual in zip(result.days, result.champion_effective_n, strict=True):
        expected = 100 * 0.5 ** (day / DECAY_HALF_LIFE_DAYS)
        assert math.isclose(actual, expected, rel_tol=1e-9)


def test_s3_steady_voting_converges_toward_the_half_life_ceiling():
    """A review voted on once a day cannot accumulate past half_life / ln 2."""
    result = S.decay_handover()
    ceiling = DECAY_HALF_LIFE_DAYS / math.log(2)
    final = result.challenger_effective_n[-1]
    assert final < ceiling
    assert final > 0.8 * ceiling


def test_s3_the_crossover_needs_no_new_champion_votes():
    """Guards the claim that recompute_all_wilson_scores is load-bearing."""
    result = S.decay_handover()
    assert all(cast == 0.0 for _, cast in result.champion_votes)


# --------------------------------------------------------------------------
# S4 — downvote raid
# --------------------------------------------------------------------------
def test_s4_raid_drives_the_score_below_the_earn_eligible_gate():
    result = S.downvote_raid()
    assert result.score_before > GATE_WILSON_LB
    assert result.score_after < GATE_WILSON_LB
    assert result.minute_below_gate is not None


def test_s4_raid_pushes_the_review_off_the_homepage():
    result = S.downvote_raid()
    assert result.rank[0] <= S.HOMEPAGE_SLOTS
    assert result.rank[-1] > S.HOMEPAGE_SLOTS


def test_s4_no_velocity_signal_fires_during_a_downvote_raid():
    """Finding F2 — fraud_service._velocity_flag filters vote == up, so a raid
    of any size is invisible to it. If this ever fails, F2 has been fixed and
    docs/RANKING_SIMULATION.md must be updated."""
    result = S.downvote_raid()
    assert result.raid_peak_hourly_downvotes_exceeds_threshold
    assert result.any_velocity_flag is False


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------
def test_scenarios_are_deterministic():
    """Charts are committed to git; a non-deterministic sim would churn them."""
    assert S.brigade_burst().target_score == S.brigade_burst().target_score
    assert S.decay_handover().champion_score == S.decay_handover().champion_score
    assert S.downvote_raid().score == S.downvote_raid().score


def test_headline_facts_cover_every_number_the_document_quotes():
    facts = S.headline_facts()
    required = {
        "wilson_5_of_5", "wilson_95_of_100", "burst_rank_before", "burst_rank_after",
        "burst_minute_entering_homepage", "decay_crossover_day",
        "raid_score_before", "raid_score_after", "raid_any_velocity_flag",
    }
    assert required <= set(facts)


# --------------------------------------------------------------------------
# End-to-end: does an influx actually reorder the feed?
# --------------------------------------------------------------------------
def _make_user(db: Session, tag: str) -> object:
    from app.models.enums import MemberRole, MemberType
    from app.models.user import User

    suffix = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(), user_id=f"usr_sim_{suffix}",
        email=f"sim_{suffix}@simulation.invalid", username=f"sim_{tag}_{suffix}",
        display_name=f"Sim {tag}", role=MemberRole.user,
        member_type=MemberType.shopper, trust_stage=2,
        verified_review_count=3, reputation_score=Decimal("75"),
    )
    db.add(user)
    return user


def _make_published_review(db: Session, product_id: uuid.UUID, author, title: str):
    from app.models.enums import EarnEligibleStatus, Verdict, VerificationStatus
    from app.models.review import Review

    suffix = uuid.uuid4().hex[:10]
    review = Review(
        id=uuid.uuid4(), review_id=f"rev_sim_{suffix}", product_id=product_id,
        author_id=author.id, title=title,
        discussion=f"Simulation fixture for {title}. " * 12,
        verdict=Verdict.yes_absolutely, target_audience="simulation",
        anti_target_audience="nobody", star_rating=5,
        pros=["fast"], cons=["none"], price_paid=Decimal("999.00"),
        verification_status=VerificationStatus.verified,
        published_at=datetime.now(UTC) - timedelta(days=10),
        earn_eligible_status=EarnEligibleStatus.none, current_version=1,
    )
    db.add(review)
    return review


def _add_votes(db: Session, review, count: int, *, positive: bool,
               spread_days: float) -> None:
    """Insert vote rows directly, back-dating created_at so decay has something
    to bite on. One fresh voter per row — uq_review_vote_once allows one vote
    per (review, voter)."""
    from app.models.enums import VoteDirection
    from app.models.vote import ReviewVote

    now = datetime.now(UTC)
    for i in range(count):
        voter = _make_user(db, "voter")
        db.flush()
        age = timedelta(days=spread_days * (i / max(1, count - 1)))
        db.add(ReviewVote(
            review_id=review.id, voter_id=voter.id,
            vote=VoteDirection.up if positive else VoteDirection.down,
            created_at=now - age,
        ))
    db.flush()


@requires_db
def test_vote_influx_reorders_the_public_feed():
    """The full production path: vote rows -> recompute -> ORDER BY wilson_score.

    Runs inside a connection-level transaction that is always rolled back, so it
    is safe against the production database: nothing is ever committed. The
    service layer's internal db.commit() releases a savepoint instead
    (join_transaction_mode="create_savepoint", SQLAlchemy 2.0).
    """
    from app.db.session import engine
    from app.models.enums import Platform, ProductStatus, VoteDirection
    from app.models.product import Product, ProductPlatform
    from app.services import review_service, vote_service

    connection = engine.connect()
    trans = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        # One product holds both reviews, so filtering the feed by product_id
        # isolates the assertion from whatever else lives in the database.
        product_id = uuid.uuid4()
        db.add(Product(
            id=product_id, product_id=f"prd_sim_{uuid.uuid4().hex[:10]}",
            canonical_name="Simulation Fixture Product", brand="SimBrand",
            category="electronics", status=ProductStatus.canonicalized,
        ))
        db.flush()
        db.add(ProductPlatform(
            product_id=product_id, platform=Platform.shopee,
            platform_url="https://shopee.ph/sim", is_monetizable=True))

        author_a = _make_user(db, "author_a")
        author_b = _make_user(db, "author_b")
        db.flush()
        control = _make_published_review(db, product_id, author_a, "Organic control")
        target = _make_published_review(db, product_id, author_b, "Brigade target")
        db.flush()

        # Control earns a solid organic history; the target starts thin.
        _add_votes(db, control, 20, positive=True, spread_days=25)
        _add_votes(db, target, 3, positive=True, spread_days=18)
        vote_service.recompute_review_vote_aggregates(db, control)
        vote_service.recompute_review_vote_aggregates(db, target)
        db.flush()

        before = review_service.list_feed(db, product_id=product_id, sort="wilson")
        order_before = [r.id for r, _, _ in before]
        assert order_before == [control.id, target.id], (
            "expected the organic control to lead before the influx")

        # One vote through the real service entry point, guards and all...
        first_brigader = _make_user(db, "brigade_lead")
        db.flush()
        vote_service.cast_vote(db, target, first_brigader, VoteDirection.up)
        # ...then the rest of the influx in bulk, finishing with the same
        # recompute the service calls.
        _add_votes(db, target, 40, positive=True, spread_days=0.007)  # ~10 minutes
        vote_service.recompute_review_vote_aggregates(db, target)
        db.flush()

        after = review_service.list_feed(db, product_id=product_id, sort="wilson")
        order_after = [r.id for r, _, _ in after]
        assert order_after == [target.id, control.id], (
            "a 41-vote influx failed to reorder the feed")
        assert float(target.wilson_score) > float(control.wilson_score)
        assert target.helpful_votes == 44  # 3 organic + 1 service + 40 bulk
    finally:
        db.close()
        trans.rollback()
        connection.close()


@requires_db
def test_fraud_signals_are_unreachable_for_a_voted_review():
    """Finding F1 — the queue's `pending` list requires published_at IS NULL
    (referral_service.py:261) while cast_vote requires published_at IS NOT NULL
    (vote_service.py:53), so a brigaded review never reaches compute_signals.

    Asserts both halves: the signal itself works when called directly, and the
    review is absent from the pending queue that is the only caller.
    """
    from app.db.session import engine
    from app.models.enums import Platform, ProductStatus
    from app.models.product import Product, ProductPlatform
    from app.services import fraud_service, referral_service, vote_service

    connection = engine.connect()
    trans = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        product_id = uuid.uuid4()
        db.add(Product(
            id=product_id, product_id=f"prd_sim_{uuid.uuid4().hex[:10]}",
            canonical_name="Signal Fixture Product", brand="SimBrand",
            category="electronics", status=ProductStatus.canonicalized,
        ))
        db.flush()
        db.add(ProductPlatform(
            product_id=product_id, platform=Platform.shopee,
            platform_url="https://shopee.ph/sim2", is_monetizable=True))
        author = _make_user(db, "author_c")
        db.flush()
        review = _make_published_review(db, product_id, author, "Brigaded review")
        db.flush()
        _add_votes(db, review, 30, positive=True, spread_days=0.007)
        vote_service.recompute_review_vote_aggregates(db, review)
        db.flush()

        # The signal is sound when it is actually invoked.
        signals = fraud_service.compute_signals(db, review, author)
        assert signals["velocity"] is True

        # But its only caller never sees this review: the pending queue is
        # unpublished-only, and an unpublished review cannot hold a vote.
        pending, _edited = referral_service.get_queue(db, limit=100)
        assert review.id not in {r.id for r in pending}
        assert all(r.published_at is None for r in pending)
    finally:
        db.close()
        trans.rollback()
        connection.close()


@requires_db
def test_votes_are_rejected_on_unpublished_reviews():
    """The other half of F1, stated directly: the queue's population is exactly
    the set of reviews that cannot be voted on."""
    from app.core.errors import NotFoundError
    from app.db.session import engine
    from app.models.enums import Platform, ProductStatus, VoteDirection
    from app.models.product import Product, ProductPlatform
    from app.services import vote_service

    connection = engine.connect()
    trans = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        product_id = uuid.uuid4()
        db.add(Product(
            id=product_id, product_id=f"prd_sim_{uuid.uuid4().hex[:10]}",
            canonical_name="Unpublished Fixture", brand="SimBrand",
            category="electronics", status=ProductStatus.canonicalized,
        ))
        db.flush()
        db.add(ProductPlatform(
            product_id=product_id, platform=Platform.shopee,
            platform_url="https://shopee.ph/sim3", is_monetizable=True))
        author = _make_user(db, "author_d")
        voter = _make_user(db, "voter_d")
        db.flush()
        review = _make_published_review(db, product_id, author, "Pending review")
        review.published_at = None  # exactly what get_queue's pending list holds
        db.flush()

        with pytest.raises(NotFoundError):
            vote_service.cast_vote(db, review, voter, VoteDirection.up)
    finally:
        db.close()
        trans.rollback()
        connection.close()
