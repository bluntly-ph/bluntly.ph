"""reputation_score, stage determination, and gate vote-weight tests (ADR-003)."""

from __future__ import annotations

import math

from app.services import trust as T


def test_reputation_bounds():
    assert T.reputation_score(0, 0, 0, 0) == 0.0
    # Max out every component: 100 helpfulness, many reviews/best answers.
    assert T.reputation_score(100, 10_000, 100, 0) == 100.0


def test_reputation_strikes_penalize():
    base = T.reputation_score(80, 10, 2, 0)
    penalized = T.reputation_score(80, 10, 2, 2)
    assert penalized == max(0.0, base - 30.0)


def test_reputation_monotonic_in_helpfulness():
    assert T.reputation_score(50, 5, 1, 0) < T.reputation_score(90, 5, 1, 0)


def test_stage_ladder():
    assert T.determine_stage(0, 0, 0, 0, 0, 0) == 0
    assert T.determine_stage(1, 0, 0, 0, 0, 0) == 1          # first review
    assert T.determine_stage(1, 1, 0, 0, 0, 0) == 2          # first verified
    assert T.determine_stage(6, 5, 75, 0, 0, 1) == 3         # >=5 verified, >=70%
    assert T.determine_stage(20, 15, 85, 3, 0, 2) == 4       # trusted
    assert T.determine_stage(60, 50, 95, 5, 0, 7) == 5       # expert


def test_stage_4_blocked_by_strike():
    assert T.determine_stage(20, 15, 85, 3, 1, 2) == 3  # a strike drops below Stage 4


def test_helpfulness_discounts_small_samples():
    """ADR-014: a lone up-vote must not score as a perfect record."""
    assert T.helpfulness_score(0, 0) == 0.0
    assert T.helpfulness_score(1, 0) == 20.65
    assert T.helpfulness_score(3, 0) == 43.85
    # Confidence grows with evidence at a constant success rate.
    assert (T.helpfulness_score(1, 0) < T.helpfulness_score(10, 0)
            < T.helpfulness_score(100, 0) < 100.0)
    # And a large good record beats a tiny perfect one — the ordering the raw
    # proportion got backwards.
    assert T.helpfulness_score(85, 15) > T.helpfulness_score(5, 0)


def test_evidence_gate_blocks_the_small_sample_exploit():
    """ADR-014: five arranged up-votes must not reach Stage 3.

    The score alone cannot stop this — 5/5 legitimately out-scores the lowered
    Stage-3 threshold — so the vote-volume gate is what has to hold.
    """
    gamer = T.determine_stage(5, 5, T.helpfulness_score(5, 0), 0, 0, 12)
    assert gamer == 3, "score ladder alone still admits the 5-vote record"
    assert T.evidence_capped_stage(gamer, total_votes=5) == 2

    # An honest reviewer with real vote volume is unaffected.
    honest = T.determine_stage(20, 20, T.helpfulness_score(85, 15), 0, 0, 12)
    assert T.evidence_capped_stage(honest, total_votes=100) == honest


def test_evidence_gate_steps_down_one_stage_at_a_time():
    # Stage 5 needs 200 votes, Stage 4 needs 60, Stage 3 needs 20.
    assert T.evidence_capped_stage(5, total_votes=200) == 5
    assert T.evidence_capped_stage(5, total_votes=199) == 4
    assert T.evidence_capped_stage(5, total_votes=59) == 3
    assert T.evidence_capped_stage(5, total_votes=19) == 2
    # Stages 0-2 gate on posting, not reception — never capped.
    assert T.evidence_capped_stage(2, total_votes=0) == 2


def test_gate_weight_probation_is_zero():
    assert T.gate_vote_weight(4, 90.0, 400, is_on_probation=True) == 0.0


def test_gate_weight_stage0_is_zero():
    assert T.gate_vote_weight(0, 100.0, 400, is_on_probation=False) == 0.0


def test_gate_weight_stage1_flat_quarter():
    assert T.gate_vote_weight(1, 50.0, 400, is_on_probation=False) == 0.25


def test_gate_weight_stage2_scales_with_trust():
    # Stage 2 multiplier 1.0 x trust% (0.8).
    assert math.isclose(T.gate_vote_weight(2, 80.0, 400, is_on_probation=False), 0.8)


def test_gate_weight_new_account_halved():
    full = T.gate_vote_weight(5, 100.0, 400, is_on_probation=False)   # 3.0 x 1.0
    young = T.gate_vote_weight(5, 100.0, 10, is_on_probation=False)   # < 30 days -> halved
    assert math.isclose(full, 3.0)
    assert math.isclose(young, 1.5)
