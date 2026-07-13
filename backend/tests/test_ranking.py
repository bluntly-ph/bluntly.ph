"""Wilson score, decay, velocity, reciprocity, gate, and phase-transition tests
(spec §3.4.1 explicitly requires Wilson and phase-transition unit tests)."""

from __future__ import annotations

import math

from app.services import ranking as R


def test_wilson_empty_is_zero():
    assert R.wilson_lower_bound(0, 0) == 0.0


def test_wilson_all_positive_below_one_and_grows_with_n():
    lb_small = R.wilson_lower_bound(5, 5)
    lb_large = R.wilson_lower_bound(100, 100)
    assert 0.0 < lb_small < lb_large < 1.0


def test_wilson_known_value():
    # 9 up / 10 total, z=1.95996 -> 0.59585 (standard Wilson LB reference).
    assert math.isclose(R.wilson_lower_bound(9, 10), 0.59585, abs_tol=1e-4)


def test_wilson_half_split_centres_below_half():
    # Symmetric data pulls the *lower* bound below 0.5.
    assert R.wilson_lower_bound(50, 100) < 0.5


def test_decay_factor_halves_at_half_life():
    assert math.isclose(R.decay_factor(R.DECAY_HALF_LIFE_DAYS), 0.5, abs_tol=1e-9)
    assert R.decay_factor(0) == 1.0


def test_time_decayed_wilson_recent_beats_old():
    recent = R.time_decayed_wilson([(True, 0)] * 20)
    old = R.time_decayed_wilson([(True, 180)] * 20)  # 4 half-lives -> weight ~1/16
    assert recent > old


def test_velocity_flag_triggers_on_burst():
    # 15 upvotes all within ~10 minutes -> exceeds 10/hour.
    burst = [float(i) for i in range(15)]  # 0..14 seconds ago
    assert R.velocity_exceeded(burst) is True


def test_velocity_flag_quiet_when_spread_out():
    # 15 upvotes spread 1 per 10 minutes -> never > 10 in any hour.
    spread = [i * 600.0 for i in range(15)]
    assert R.velocity_exceeded(spread) is False


def test_velocity_below_threshold_never_flags():
    assert R.velocity_exceeded([1.0, 2.0, 3.0]) is False


def test_reciprocity_requires_min_sample():
    assert R.reciprocity_flag(shared_targets=4, reciprocal_pairs=4) is False
    assert R.reciprocity_flag(shared_targets=10, reciprocal_pairs=7) is True
    assert R.reciprocity_flag(shared_targets=10, reciprocal_pairs=6) is False  # exactly 0.6, not >


def test_gate_passes_requires_both_conditions():
    # High agreement, enough voters -> passes.
    assert R.gate_passes(20, 20, stage2_plus_voters=3) is True
    # Same score but too few voters -> fails.
    assert R.gate_passes(20, 20, stage2_plus_voters=2) is False
    # Enough voters but weak score -> fails.
    assert R.gate_passes(6, 10, stage2_plus_voters=5) is False


def test_phase_transition_at_fifty():
    assert R.is_post_seeding(49) is False
    assert R.is_post_seeding(50) is True
    assert R.is_post_seeding(51) is True
