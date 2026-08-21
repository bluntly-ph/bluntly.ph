"""The Wilson ranking, checked as properties.

This decides the order every reader sees, so the things that must be true of it
are worth stating as tests rather than trusting to the formula being copied
correctly:

  * the score is always a probability, never NaN;
  * more positive votes never lower it;
  * the same ratio with more votes never lowers it — that is the whole reason
    for a lower bound rather than a plain proportion;
  * a vote's weight halves every half-life, exactly.

`wilson_lower_bound` also used to raise `ValueError` when `positive > total`:
`phat > 1` puts a negative under the square root. Nothing reached it — both
callers clamp or construct their inputs safely — but the precondition belongs
with the function that needs it rather than with each caller who has to
remember, and the failure would have been a 500 out of a nightly sweep.
"""

from __future__ import annotations

import math
import random

import pytest

from app.services.ranking import (
    DECAY_HALF_LIFE_DAYS,
    decay_factor,
    time_decayed_wilson,
    wilson_lower_bound,
)


class TestItIsAlwaysAProbability:

    def test_over_a_wide_random_spread(self):
        rng = random.Random(11)
        for _ in range(5000):
            total = rng.randint(1, 5000)
            positive = rng.randint(0, total)
            score = wilson_lower_bound(positive, total)
            assert 0.0 <= score <= 1.0 and not math.isnan(score), (positive, total)

    @pytest.mark.parametrize("positive,total", [
        (5, 3),                     # more positives than votes
        (-1, 10),                   # negative count
        (0, -5),                    # negative total
        (float("inf"), 10),
        (1, float("inf")),
        (float("nan"), 10),
    ])
    def test_hostile_inputs_produce_a_number_not_an_exception(self, positive, total):
        score = wilson_lower_bound(positive, total)
        assert 0.0 <= score <= 1.0 and not math.isnan(score)

    def test_empty_and_unanimous_ends(self):
        assert wilson_lower_bound(0, 0) == 0.0
        assert wilson_lower_bound(0, 100) == 0.0
        assert 0.0 < wilson_lower_bound(100, 100) < 1.0


class TestOrdering:

    @pytest.mark.parametrize("total", [5, 50, 500])
    def test_more_positives_never_lowers_the_score(self, total):
        previous = -1.0
        for positive in range(total + 1):
            score = wilson_lower_bound(positive, total)
            assert score >= previous - 1e-12, (positive, total)
            previous = score

    @pytest.mark.parametrize("ratio", [0.6, 0.8, 0.95])
    def test_the_same_ratio_with_more_votes_never_lowers_it(self, ratio):
        """Why this is a lower bound and not a proportion: 9/10 must not
        outrank 900/1000."""
        previous = -1.0
        for total in (10, 50, 200, 1000, 5000):
            score = wilson_lower_bound(ratio * total, total)
            assert score >= previous - 1e-12, (ratio, total)
            previous = score

    def test_a_small_perfect_record_does_not_beat_a_large_good_one(self):
        assert wilson_lower_bound(1, 1) < wilson_lower_bound(90, 100)

    def test_the_documented_value_still_holds(self):
        """ADR-014's example, quoted in helpfulness_score's docstring."""
        assert round(100.0 * wilson_lower_bound(1, 1), 2) == 20.65


class TestRecencyDecay:

    def test_a_fresh_vote_counts_fully(self):
        assert decay_factor(0) == 1.0

    def test_one_half_life_halves_it(self):
        assert decay_factor(DECAY_HALF_LIFE_DAYS) == pytest.approx(0.5)

    def test_weight_never_reaches_zero(self):
        """Old votes fade; they do not vanish and take the denominator with them."""
        assert decay_factor(50 * DECAY_HALF_LIFE_DAYS) > 0.0

    def test_stale_negatives_weigh_less_than_fresh_positives(self):
        fresh = time_decayed_wilson([(True, 0.0)] * 10 + [(False, 0.0)] * 2)
        buried = time_decayed_wilson(
            [(True, 0.0)] * 10 + [(False, 0.0)] * 2
            + [(False, 10 * DECAY_HALF_LIFE_DAYS)] * 50)
        assert fresh > buried, "old votes are not decaying"

    def test_no_votes_scores_zero(self):
        assert time_decayed_wilson([]) == 0.0
