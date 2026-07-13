"""Ranking & fraud-signal math (ADR-004).

Pure, deterministic, side-effect-free functions — the spec (§3.4.1) explicitly
requires unit tests for Wilson computation and phase-transition detection, so all
parameters are pinned numerically here rather than left as prose.

Pinned parameters (ADR-004):
  * Confidence: z = 1.95996 (two-sided 95%).
  * Time-decay: exponential, half-life = 45 days.
  * Velocity flag: > 10 upvotes within a 3600s (1h) sliding window.
  * Reciprocity flag: pairwise reciprocal rate > 0.60 over >= 5 shared targets.
  * Post-Seeding gate: Wilson LB (on effective n) >= 0.65 AND >= 3 Stage-2+ voters.
  * Phase transition: >= 50 Stage-2+ verified reviewers in the pilot category.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

# --- Pinned parameters ---
WILSON_Z_95 = 1.95996398454
DECAY_HALF_LIFE_DAYS = 45.0
VELOCITY_WINDOW_SECONDS = 3600
VELOCITY_THRESHOLD = 10
RECIPROCITY_MIN_SHARED = 5
RECIPROCITY_THRESHOLD = 0.60
GATE_WILSON_LB = 0.65
GATE_MIN_STAGE2_VOTERS = 3
SEEDING_TRANSITION_REVIEWERS = 50


def wilson_lower_bound(positive: float, total: float, z: float = WILSON_Z_95) -> float:
    """Wilson score interval lower bound for a Bernoulli proportion.

    Accepts weighted (non-integer) counts so it can run on effective n.
    Returns 0.0 for empty input.
    """
    if total <= 0:
        return 0.0
    phat = positive / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = phat + z2 / (2.0 * total)
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * total)) / total)
    return max(0.0, (centre - margin) / denom)


def decay_factor(age_days: float, half_life_days: float = DECAY_HALF_LIFE_DAYS) -> float:
    """Exponential recency weight in (0, 1]. age 0 -> 1.0; one half-life -> 0.5."""
    if age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def time_decayed_wilson(
    votes: Iterable[tuple[bool, float]],
    z: float = WILSON_Z_95,
    half_life_days: float = DECAY_HALF_LIFE_DAYS,
) -> float:
    """Wilson lower bound over recency-weighted votes.

    `votes` is an iterable of (is_positive, age_days). Each vote contributes its
    decay weight to the totals, so older votes count less.
    """
    positive = 0.0
    total = 0.0
    for is_positive, age_days in votes:
        w = decay_factor(age_days, half_life_days)
        total += w
        if is_positive:
            positive += w
    return wilson_lower_bound(positive, total, z)


def velocity_exceeded(
    upvote_ages_seconds: Sequence[float],
    window_seconds: int = VELOCITY_WINDOW_SECONDS,
    threshold: int = VELOCITY_THRESHOLD,
) -> bool:
    """True if > `threshold` upvotes fall within any `window_seconds` window.

    `upvote_ages_seconds` = seconds-ago for each upvote. Uses a sliding window
    over the sorted ages; advisory only (never auto-blocks — fraud layer 5).
    """
    if len(upvote_ages_seconds) <= threshold:
        return False
    ages = sorted(upvote_ages_seconds)
    left = 0
    for right in range(len(ages)):
        while ages[right] - ages[left] > window_seconds:
            left += 1
        if (right - left + 1) > threshold:
            return True
    return False


def reciprocity_flag(
    shared_targets: int,
    reciprocal_pairs: int,
    min_shared: int = RECIPROCITY_MIN_SHARED,
    threshold: float = RECIPROCITY_THRESHOLD,
) -> bool:
    """Pairwise collusion signal (fraud layer, advisory).

    `shared_targets` = content both voters voted on; `reciprocal_pairs` = of those,
    how many were mutual upvotes. Flags only above a minimum sample.
    """
    if shared_targets < min_shared:
        return False
    return (reciprocal_pairs / shared_targets) > threshold


def gate_passes(effective_positive: float, effective_total: float,
                stage2_plus_voters: int) -> bool:
    """Post-Seeding auto-queue gate: Wilson LB (effective n) >= 0.65 AND >= 3 Stage-2+ voters."""
    lb = wilson_lower_bound(effective_positive, effective_total)
    return lb >= GATE_WILSON_LB and stage2_plus_voters >= GATE_MIN_STAGE2_VOTERS


def is_post_seeding(stage2_plus_reviewers: int) -> bool:
    """Phase-transition detection at the 50 Stage-2+ reviewer threshold (§3.4.1)."""
    return stage2_plus_reviewers >= SEEDING_TRANSITION_REVIEWERS
