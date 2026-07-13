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
