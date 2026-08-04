"""Helpfulness as a raw proportion vs. a Wilson lower bound (FINDING-1).

PROPOSAL EVIDENCE, NOT SHIPPED BEHAVIOUR. Nothing in `app/` calls this. It exists
to demonstrate a defect in the shipped `helpfulness_ratio` and to derive the
re-calibrated trust-stage thresholds its fix requires. See
`docs/2026-08-03-algorithm-decisions.md` FINDING-1.

The defect: `trust_service.recompute_user_trust` sets

    helpfulness = 100 * helpful / (helpful + unhelpful)

a raw proportion with no confidence correction, so one upvote and zero downvotes
scores 100.0. That feeds 60% of `reputation_score` (ADR-003), which gates
`determine_stage`, which sets `gate_vote_weight` — so five arranged votes buy a
full-strength vote on the earn-eligible gate that pays out the Honesty Fund.

The fix reuses `ranking.wilson_lower_bound` — the same estimator ADR-004 already
applies to *reviews*, applied to the *reviewer*. Small samples are discounted;
sustained performance is not.

The cost: the stage thresholds (70/80/90) were calibrated against a raw
proportion and are far stricter under a lower bound. `recalibrate()` derives
replacements that hold the intended honest cohort at its historical pass rate.

Pure and deterministic: fixed-seed `random.Random(SEED)`, no clock, no database.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.services.ranking import wilson_lower_bound
from app.services.trust import (
    determine_stage,
    evidence_capped_stage,
    gate_vote_weight,
    reputation_score,
)

SEED = 42
REPS = 4000

# Votes an average published review attracts. The recalibration below is
# sensitive to this; `threshold_sensitivity()` reports how much.
VOTES_PER_REVIEW = 8

# Share of honest reviewers at the target performance who must still clear the
# bar. 0.10 => the 10th percentile of the honest cohort sits at the threshold.
HONEST_PASS_QUANTILE = 0.10

# Minimum-evidence gate: average up-votes per verified review a stage requires.
# A score threshold cannot do this job on its own — see `recalibrate`.
MIN_VOTES_PER_REVIEW = 4

# (stage, verified reviews required, true helpfulness the stage intends)
STAGE_INTENT = (
    (3, 5, 0.75),
    (4, 15, 0.85),
    (5, 50, 0.95),
)

# What the thresholds were before ADR-014, kept here only so the before/after
# comparison stays readable. The live values are trust.STAGE{3,4,5}_HELPFULNESS.
PRE_ADR014_THRESHOLDS = {3: 70.0, 4: 80.0, 5: 90.0}


def naive_helpfulness(helpful: int, total: int) -> float:
    """Shipped behaviour: raw proportion, 0-100."""
    return 100.0 * helpful / total if total else 0.0


def wilson_helpfulness(helpful: int, total: int) -> float:
    """Proposed: Wilson lower bound on the same counts, 0-100."""
    return 100.0 * wilson_lower_bound(helpful, total)


@dataclass(frozen=True)
class Profile:
    """A reviewer's standing under one helpfulness estimator."""

    helpfulness: float
    reputation: float
    stage: int
    vote_weight: float


def profile(helpfulness: float, verified_reviews: int, total_votes: int, *,
            best_answers: int = 0, strikes: int = 0, months_active: float = 12.0,
            account_age_days: int = 365, apply_gate: bool = True) -> Profile:
    """Push a helpfulness value through the real ADR-003 + ADR-014 chain.

    `apply_gate=False` reproduces the shipped pre-ADR-014 path (score ladder
    only), which is what the "shipped" rows below model.
    """
    rep = reputation_score(helpfulness_ratio=helpfulness,
                           verified_review_count=verified_reviews,
                           best_answer_count=best_answers, strikes=strikes)
    stage = determine_stage(review_count=verified_reviews,
                            verified_review_count=verified_reviews,
                            helpfulness_ratio=helpfulness,
                            best_answer_count=best_answers, strikes=strikes,
                            months_active=months_active)
    if apply_gate:
        stage = evidence_capped_stage(stage, total_votes=total_votes)
    weight = gate_vote_weight(trust_stage=stage, reputation_score_value=rep,
                              account_age_days=account_age_days,
                              is_on_probation=False)
    return Profile(helpfulness, rep, stage, weight)


def gamer_vs_honest() -> tuple[Profile, Profile, Profile, Profile]:
    """The exploit and its honest counterpart, before and after ADR-014.

    Gamer: 5 verified reviews, one arranged up-vote each (5 votes total).
    Honest: 20 verified reviews, 85 helpful of 100 votes.

    Note the fix is the *pair*: at the ADR-014 thresholds the gamer's Wilson
    score (56.55) still clears Stage 3 on the ladder alone — `apply_gate` is
    what actually demotes it.
    """
    gamer_before = profile(naive_helpfulness(5, 5), 5, 5, apply_gate=False)
    gamer_after = profile(wilson_helpfulness(5, 5), 5, 5)
    honest_before = profile(naive_helpfulness(85, 100), 20, 100, apply_gate=False)
    honest_after = profile(wilson_helpfulness(85, 100), 20, 100)
    return gamer_before, gamer_after, honest_before, honest_after


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def honest_cohort(reviews: int, true_rate: float, *,
                  votes_per_review: int = VOTES_PER_REVIEW,
                  reps: int = REPS) -> list[float]:
    """Wilson helpfulness for `reps` honest reviewers of identical true skill."""
    rng = random.Random(SEED)
    n = reviews * votes_per_review
    return [wilson_helpfulness(sum(1 for _ in range(n) if rng.random() < true_rate), n)
            for _ in range(reps)]


def recalibrate(*, votes_per_review: int = VOTES_PER_REVIEW) -> list[tuple]:
    """Thresholds holding the honest cohort at HONEST_PASS_QUANTILE.

    Returns (stage, current_threshold, proposed, min_votes, gamer_score).

    NOTE the threshold alone does not stop the exploit: a *perfect* small record
    outscores a *mediocre* large one, which is correct inference but means a
    lowered threshold re-admits the gamer. `min_votes` is the necessary second
    guard — a minimum-evidence gate no score can substitute for.
    """
    out = []
    for stage, reviews, rate in STAGE_INTENT:
        cohort = honest_cohort(reviews, rate, votes_per_review=votes_per_review)
        proposed = _quantile(cohort, HONEST_PASS_QUANTILE)
        min_votes = MIN_VOTES_PER_REVIEW * reviews
        gamer = wilson_helpfulness(reviews, reviews)
        out.append((stage, PRE_ADR014_THRESHOLDS[stage], proposed, min_votes, gamer))
    return out


def arranged_votes_needed(*, votes_per_review: int = VOTES_PER_REVIEW) -> list[tuple]:
    """Distinct arranged up-votes an attacker must buy to reach each stage.

    Shipped: the raw proportion is 100.0 at any volume, so one vote per review
    clears every helpfulness bar. Fixed: the attacker must satisfy BOTH the
    Wilson threshold and the minimum-evidence gate.
    """
    out = []
    for stage, _cur, proposed, min_votes, _ in recalibrate(votes_per_review=votes_per_review):
        reviews = dict((s, r) for s, r, _ in STAGE_INTENT)[stage]
        needed = min_votes
        while wilson_helpfulness(needed, needed) < proposed:
            needed += 1
        out.append((stage, reviews, needed, needed / reviews))
    return out


def threshold_sensitivity(options: tuple[int, ...] = (4, 8, 16)) -> list[tuple]:
    """How much the proposed thresholds move with the votes/review assumption."""
    return [(v, [round(row[2], 1) for row in recalibrate(votes_per_review=v)])
            for v in options]


def main() -> None:
    print("1. THE DEFECT — 5 arranged votes vs. 100 real ones")
    g_before, g_after, h_before, h_after = gamer_vs_honest()
    print(f"{'':22} {'helpful':>8} {'reput.':>8} {'stage':>6} {'weight':>8}")
    for label, p in (("gamer   (before)", g_before), ("honest  (before)", h_before),
                     ("gamer   (ADR-014)", g_after), ("honest  (ADR-014)", h_after)):
        print(f"  {label:<20} {p.helpfulness:>8.2f} {p.reputation:>8.2f} "
              f"{p.stage:>6} {p.vote_weight:>8.4f}")
    print(f"  before:  gamer outranks honest by "
          f"{g_before.reputation - h_before.reputation:+.2f} reputation")
    print(f"  ADR-014: gamer trails honest by "
          f"{g_after.reputation - h_after.reputation:+.2f} reputation, and is")
    print(f"           demoted to stage {g_after.stage} by the evidence gate "
          "(the score alone still clears 3)")

    print("\n2. RECALIBRATED THRESHOLDS + MINIMUM-EVIDENCE GATE "
          f"({VOTES_PER_REVIEW} votes/review, {int(HONEST_PASS_QUANTILE * 100)}th pct)")
    print(f"{'stage':>6} {'was':>9} {'shipped':>9} {'min votes':>10} {'gamer':>8}")
    for stage, cur, proposed, min_votes, gamer in recalibrate():
        verdict = "blocked by gate" if gamer >= proposed else "blocked by score"
        print(f"{stage:>6} {cur:>9.0f} {proposed:>9.1f} {min_votes:>10} {gamer:>8.1f}"
              f"   <- {verdict}")
    print("  The gamer out-scores the lowered threshold at every stage: the score")
    print("  alone does NOT stop it. The minimum-evidence gate is what does.")

    print("\n3. ATTACKER COST — arranged up-votes needed per stage")
    print(f"{'stage':>6} {'reviews':>8} {'shipped':>9} {'fixed':>7} {'votes/review':>13}")
    for stage, reviews, needed, per_review in arranged_votes_needed():
        print(f"{stage:>6} {reviews:>8} {reviews:>9} {needed:>7} {per_review:>13.1f}")
    print("  Cost rises but is not eliminated — an attacker with enough distinct")
    print("  qualified voters still climbs. The residual is what the existing")
    print("  velocity and collusion signals (ADR-004) are there to catch.")

    print("\n4. SENSITIVITY to the votes/review assumption")
    for votes, thresholds in threshold_sensitivity():
        print(f"  {votes:>3} votes/review -> stage 3/4/5 thresholds {thresholds}")


if __name__ == "__main__":
    main()
