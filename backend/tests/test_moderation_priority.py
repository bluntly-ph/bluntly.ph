"""Pure policy tests for the canonical review-priority evaluator (design §5).

No database is used anywhere in this module — ``evaluate_priority`` is a pure
function over already-loaded facts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models.enums import ModerationReason
from app.services.moderation_priority import (
    POLICY_VERSION,
    PriorityAssessment,
    PriorityBand,
    PriorityFacts,
    PriorityLane,
    SlaState,
    evaluate_priority,
)

NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _facts(**overrides) -> PriorityFacts:
    base = dict(
        queued_at=NOW - timedelta(minutes=1),
        report_count=0,
        report_reasons=frozenset(),
        edited_since_monetized=False,
        velocity=False,
        collusion=False,
        duplicate_content=False,
        manually_escalated=False,
    )
    base.update(overrides)
    return PriorityFacts(**base)


# --------------------------------------------------------------------------- #
# Pinned specification examples
# --------------------------------------------------------------------------- #

def test_collusion_and_duplicate_are_additive_but_score_is_capped():
    facts = PriorityFacts(
        queued_at=NOW - timedelta(hours=1),
        report_count=4,
        report_reasons=frozenset({ModerationReason.fake_proof}),
        edited_since_monetized=True,
        velocity=True,
        collusion=True,
        duplicate_content=True,
        manually_escalated=False,
    )
    result = evaluate_priority(facts, now=NOW)
    assert result.policy_version == "review-priority-v1"
    assert result.integrity_score == 100
    assert result.lane == PriorityLane.reported
    assert [f.code for f in result.factors] == [
        "edited_after_monetization", "collusion", "duplicate_content",
        "vote_velocity", "report_count_4_plus", "report_reason_fake_proof",
    ]


def test_non_inputs_never_appear_in_priority_facts_or_assessment():
    forbidden = {
        "active_ms", "body_active_ms", "scroll_milestone", "first_vote_at",
        "country", "wilson_score", "reputation_score", "trust_stage",
        "verification_status", "star_rating",
    }
    assert forbidden.isdisjoint(PriorityFacts.__dataclass_fields__)
    assert forbidden.isdisjoint(PriorityAssessment.__dataclass_fields__)


# --------------------------------------------------------------------------- #
# Individual factor contributions
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("field", "code", "contribution"),
    [
        ("edited_since_monetized", "edited_after_monetization", 40),
        ("collusion", "collusion", 35),
        ("duplicate_content", "duplicate_content", 30),
        ("velocity", "vote_velocity", 15),
    ],
)
def test_each_boolean_factor_contributes_alone(field, code, contribution):
    facts = _facts(**{field: True})
    result = evaluate_priority(facts, now=NOW)
    assert [f.code for f in result.factors] == [code]
    assert result.factors[0].observed is True
    assert result.factors[0].contribution == contribution
    assert result.integrity_score == contribution


def test_no_factors_fire_when_nothing_is_reported_or_flagged():
    result = evaluate_priority(_facts(), now=NOW)
    assert result.factors == ()
    assert result.integrity_score == 0


# --------------------------------------------------------------------------- #
# Report-count bracket: only the highest bracket applies
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("report_count", "code", "contribution"),
    [
        (1, "report_count_1", 15),
        (2, "report_count_2_3", 25),
        (3, "report_count_2_3", 25),
        (4, "report_count_4_plus", 35),
        (9, "report_count_4_plus", 35),
    ],
)
def test_report_count_bracket_is_highest_only(report_count, code, contribution):
    facts = _facts(report_count=report_count)
    result = evaluate_priority(facts, now=NOW)
    assert [f.code for f in result.factors] == [code]
    assert result.factors[0].observed == report_count
    assert result.factors[0].contribution == contribution


def test_zero_reports_produce_no_report_count_factor():
    result = evaluate_priority(_facts(report_count=0), now=NOW)
    assert result.factors == ()


# --------------------------------------------------------------------------- #
# Report-reason tier: only the highest tier applies, regardless of volume
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("reasons", "code", "contribution"),
    [
        ({ModerationReason.fake_proof}, "report_reason_fake_proof", 20),
        ({ModerationReason.harassment}, "report_reason_harassment", 20),
        ({ModerationReason.seller_posing_as_buyer}, "report_reason_seller_posing_as_buyer", 15),
        ({ModerationReason.plagiarized}, "report_reason_plagiarized", 15),
        ({ModerationReason.conflict_of_interest}, "report_reason_conflict_of_interest", 10),
        ({ModerationReason.spam}, "report_reason_spam", 5),
        ({ModerationReason.other}, "report_reason_other", 0),
    ],
)
def test_report_reason_tier_contribution(reasons, code, contribution):
    facts = _facts(report_count=1, report_reasons=frozenset(reasons))
    result = evaluate_priority(facts, now=NOW)
    codes = [f.code for f in result.factors]
    assert code in codes
    reason_factor = next(f for f in result.factors if f.code == code)
    assert reason_factor.contribution == contribution


def test_only_the_highest_report_reason_tier_applies_regardless_of_count():
    facts = _facts(
        report_count=9,
        report_reasons=frozenset({
            ModerationReason.spam, ModerationReason.other, ModerationReason.fake_proof,
        }),
    )
    result = evaluate_priority(facts, now=NOW)
    reason_codes = [f.code for f in result.factors if f.code.startswith("report_reason_")]
    assert reason_codes == ["report_reason_fake_proof"]
    reason_factor = next(f for f in result.factors if f.code == "report_reason_fake_proof")
    assert reason_factor.contribution == 20


def test_report_reason_tie_within_a_tier_is_deterministic():
    facts = _facts(
        report_count=1,
        report_reasons=frozenset({ModerationReason.harassment, ModerationReason.fake_proof}),
    )
    a = evaluate_priority(facts, now=NOW)
    b = evaluate_priority(facts, now=NOW)
    assert a.factors == b.factors
    codes = [f.code for f in a.factors if f.code.startswith("report_reason_")]
    assert codes == ["report_reason_fake_proof"]


def test_no_reasons_produce_no_report_reason_factor():
    result = evaluate_priority(_facts(report_count=1, report_reasons=frozenset()), now=NOW)
    assert all(not f.code.startswith("report_reason_") for f in result.factors)


# --------------------------------------------------------------------------- #
# Score cap
# --------------------------------------------------------------------------- #

def test_score_never_exceeds_100():
    facts = _facts(
        report_count=9,
        report_reasons=frozenset({ModerationReason.fake_proof}),
        edited_since_monetized=True,
        velocity=True,
        collusion=True,
        duplicate_content=True,
    )
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 100


# --------------------------------------------------------------------------- #
# Lane precedence: escalated > reported > integrity > routine
# --------------------------------------------------------------------------- #

def test_lane_escalated_wins_over_everything():
    facts = _facts(report_count=9, collusion=True, manually_escalated=True)
    result = evaluate_priority(facts, now=NOW)
    assert result.lane == PriorityLane.escalated


def test_lane_reported_wins_over_integrity_advisories():
    facts = _facts(report_count=1, collusion=True, duplicate_content=True)
    result = evaluate_priority(facts, now=NOW)
    assert result.lane == PriorityLane.reported


@pytest.mark.parametrize(
    "field", ["edited_since_monetized", "velocity", "collusion", "duplicate_content"],
)
def test_lane_integrity_when_no_reports_or_escalation(field):
    facts = _facts(**{field: True})
    result = evaluate_priority(facts, now=NOW)
    assert result.lane == PriorityLane.integrity


def test_lane_routine_when_nothing_fires():
    result = evaluate_priority(_facts(), now=NOW)
    assert result.lane == PriorityLane.routine


# --------------------------------------------------------------------------- #
# SLA boundaries: 1h escalated, 4h reported, 8h integrity, 24h routine
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("facts_kwargs", "target_hours"),
    [
        (dict(manually_escalated=True), 1),
        (dict(report_count=1), 4),
        (dict(collusion=True), 8),
        (dict(), 24),
    ],
)
def test_sla_on_track_below_approaching_threshold(facts_kwargs, target_hours):
    queued_at = NOW - timedelta(hours=target_hours * 0.75) + timedelta(minutes=1)
    facts = _facts(queued_at=queued_at, **facts_kwargs)
    result = evaluate_priority(facts, now=NOW)
    assert result.sla_state == SlaState.on_track
    assert result.due_at == queued_at + timedelta(hours=target_hours)


@pytest.mark.parametrize(
    ("facts_kwargs", "target_hours"),
    [
        (dict(manually_escalated=True), 1),
        (dict(report_count=1), 4),
        (dict(collusion=True), 8),
        (dict(), 24),
    ],
)
def test_sla_approaching_at_exactly_75_percent(facts_kwargs, target_hours):
    queued_at = NOW - timedelta(hours=target_hours * 0.75)
    facts = _facts(queued_at=queued_at, **facts_kwargs)
    result = evaluate_priority(facts, now=NOW)
    assert result.sla_state == SlaState.approaching


@pytest.mark.parametrize(
    ("facts_kwargs", "target_hours"),
    [
        (dict(manually_escalated=True), 1),
        (dict(report_count=1), 4),
        (dict(collusion=True), 8),
        (dict(), 24),
    ],
)
def test_sla_overdue_at_exactly_the_target(facts_kwargs, target_hours):
    queued_at = NOW - timedelta(hours=target_hours)
    facts = _facts(queued_at=queued_at, **facts_kwargs)
    result = evaluate_priority(facts, now=NOW)
    assert result.sla_state == SlaState.overdue


def test_sla_uses_queue_time_not_a_different_clock():
    facts = _facts(queued_at=NOW - timedelta(hours=25))
    result = evaluate_priority(facts, now=NOW)
    assert result.sla_state == SlaState.overdue
    assert result.due_at == facts.queued_at + timedelta(hours=24)


# --------------------------------------------------------------------------- #
# Band thresholds: high >= 40 or overdue or escalated; normal 15-39 or approaching
# --------------------------------------------------------------------------- #

def test_band_low_below_15_and_on_track():
    facts = _facts(queued_at=NOW - timedelta(minutes=1))
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 0
    assert result.band == PriorityBand.low


def test_band_normal_at_score_15():
    facts = _facts(report_count=1, queued_at=NOW - timedelta(minutes=1))
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 15
    assert result.band == PriorityBand.normal


def test_band_normal_just_below_high_threshold():
    # Every contribution is a multiple of 5, so 35 (not 39) is the score
    # directly below the 40-point high threshold that this policy can produce.
    facts = _facts(collusion=True, queued_at=NOW - timedelta(minutes=1))
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 35
    assert result.band == PriorityBand.normal


def test_band_high_at_score_40():
    facts = _facts(edited_since_monetized=True, queued_at=NOW - timedelta(minutes=1))
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 40
    assert result.band == PriorityBand.high


def test_band_normal_when_approaching_sla_even_with_zero_score():
    queued_at = NOW - timedelta(hours=18)  # 75% of the 24h routine target
    facts = _facts(queued_at=queued_at)
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 0
    assert result.sla_state == SlaState.approaching
    assert result.band == PriorityBand.normal


def test_band_high_when_overdue_even_with_zero_score():
    queued_at = NOW - timedelta(hours=24)
    facts = _facts(queued_at=queued_at)
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 0
    assert result.sla_state == SlaState.overdue
    assert result.band == PriorityBand.high


def test_band_high_when_escalated_even_with_zero_score_and_on_track():
    facts = _facts(manually_escalated=True, queued_at=NOW - timedelta(minutes=1))
    result = evaluate_priority(facts, now=NOW)
    assert result.integrity_score == 0
    assert result.sla_state == SlaState.on_track
    assert result.band == PriorityBand.high


# --------------------------------------------------------------------------- #
# Deterministic ordering
# --------------------------------------------------------------------------- #

def test_order_key_shape():
    result = evaluate_priority(_facts(), now=NOW)
    lane_rank, sla_rank, neg_score, due_at, queued_at = result.order_key
    assert isinstance(lane_rank, int)
    assert isinstance(sla_rank, int)
    assert isinstance(neg_score, int)
    assert isinstance(due_at, datetime)
    assert isinstance(queued_at, datetime)


def test_order_key_prefers_earlier_lane_rank():
    escalated = evaluate_priority(_facts(manually_escalated=True), now=NOW)
    routine = evaluate_priority(_facts(), now=NOW)
    assert escalated.order_key < routine.order_key


def test_order_key_prefers_overdue_before_approaching_before_on_track():
    overdue = evaluate_priority(_facts(queued_at=NOW - timedelta(hours=24)), now=NOW)
    approaching = evaluate_priority(_facts(queued_at=NOW - timedelta(hours=18)), now=NOW)
    on_track = evaluate_priority(_facts(queued_at=NOW - timedelta(hours=1)), now=NOW)
    assert overdue.order_key < approaching.order_key < on_track.order_key


def test_order_key_prefers_higher_integrity_score_within_same_lane_and_sla():
    higher = evaluate_priority(_facts(collusion=True, queued_at=NOW - timedelta(minutes=1)),
                                now=NOW)
    lower = evaluate_priority(_facts(velocity=True, queued_at=NOW - timedelta(minutes=1)),
                               now=NOW)
    assert higher.integrity_score > lower.integrity_score
    assert higher.order_key < lower.order_key


def test_order_key_ties_when_lane_sla_score_due_and_queued_all_match():
    """Two different report reasons in the same tier score identically, so
    their order keys tie even though their factor codes differ — the caller
    (Task 2) is expected to break the tie with the queue-entry UUID."""
    queued_at = NOW - timedelta(minutes=1)
    fake_proof = evaluate_priority(
        _facts(queued_at=queued_at, report_count=1,
               report_reasons=frozenset({ModerationReason.fake_proof})),
        now=NOW,
    )
    harassment = evaluate_priority(
        _facts(queued_at=queued_at, report_count=1,
               report_reasons=frozenset({ModerationReason.harassment})),
        now=NOW,
    )
    assert [f.code for f in fake_proof.factors] != [f.code for f in harassment.factors]
    assert fake_proof.integrity_score == harassment.integrity_score
    assert fake_proof.order_key == harassment.order_key


def test_order_key_is_repeatable_for_identical_facts():
    queued_at = NOW - timedelta(minutes=1)
    first = evaluate_priority(_facts(queued_at=queued_at, velocity=True), now=NOW)
    second = evaluate_priority(_facts(queued_at=queued_at, velocity=True), now=NOW)
    assert first.order_key == second.order_key


# --------------------------------------------------------------------------- #
# Naive datetimes are rejected
# --------------------------------------------------------------------------- #

def test_naive_queued_at_raises_value_error():
    facts = _facts(queued_at=datetime(2026, 9, 8, 11, 0, 0))
    with pytest.raises(ValueError, match="queued_at"):
        evaluate_priority(facts, now=NOW)


def test_naive_now_raises_value_error():
    with pytest.raises(ValueError, match="now"):
        evaluate_priority(_facts(), now=datetime(2026, 9, 8, 12, 0, 0))


# --------------------------------------------------------------------------- #
# Non-UTC but timezone-aware datetimes are normalized to UTC
# --------------------------------------------------------------------------- #

def test_aware_non_utc_input_is_normalized_to_utc_due_at_and_order_key():
    """A UTC+08:00 caller must get exactly the same assessment as the UTC
    equivalent instant — normalized to UTC, not merely accepted as-is."""
    plus8 = timezone(timedelta(hours=8))
    queued_at_plus8 = (NOW - timedelta(hours=1)).astimezone(plus8)
    now_plus8 = NOW.astimezone(plus8)
    assert queued_at_plus8.utcoffset() == timedelta(hours=8)  # sanity: not already UTC

    facts_plus8 = _facts(queued_at=queued_at_plus8, report_count=1, collusion=True)
    facts_utc = _facts(queued_at=NOW - timedelta(hours=1), report_count=1, collusion=True)

    result_plus8 = evaluate_priority(facts_plus8, now=now_plus8)
    result_utc = evaluate_priority(facts_utc, now=NOW)

    # Same instant, same assessment.
    assert result_plus8 == result_utc

    # And the output timestamps are concretely UTC, not merely equal instants
    # expressed in another offset.
    assert result_plus8.due_at.tzinfo == UTC
    assert result_plus8.due_at.utcoffset() == timedelta(0)
    order_key_due_at = result_plus8.order_key[3]
    order_key_queued_at = result_plus8.order_key[4]
    assert order_key_due_at.tzinfo == UTC
    assert order_key_queued_at.tzinfo == UTC


def test_policy_version_constant():
    assert POLICY_VERSION == "review-priority-v1"
