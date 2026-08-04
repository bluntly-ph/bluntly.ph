"""Trust progression & incentive math (ADR-003).

Pure functions. `reputation_score` (the spec's undefined "trust score percentage",
A1) is defined here as a deterministic 0-100 blend so gate vote weights are
testable. Weights are pinned and documented in ADR-003.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.core.constants import ACCOUNT_MATURATION_DAYS, honesty_price_multiplier
from app.services.ranking import wilson_lower_bound

# --- reputation_score weights (ADR-003); components cap at 100 total ---
W_HELPFULNESS = 0.60          # up to 60 pts from helpfulness ratio (0-100)
VOLUME_CAP = 25.0             # up to 25 pts from verified-review volume
VOLUME_COEFF = 10.0           # 10 * log10(1 + n)
BEST_ANSWER_CAP = 15.0        # up to 15 pts from Best Answers
BEST_ANSWER_COEFF = 3.0
STRIKE_PENALTY = 15.0         # per strike

# --- Gate vote-weight multipliers per trust stage (FR-7) ---
STAGE_MULTIPLIER = {0: 0.0, 1: 0.25, 2: 1.0, 3: 1.5, 4: 2.0, 5: 3.0}

# --- Stage helpfulness thresholds (ADR-014) ---
# Re-derived for the Wilson lower bound, which is far stricter than the raw
# proportion these replaced (70/80/90). Values hold the modelled honest cohort at
# its historical pass rate; re-tune from real vote data as it arrives.
STAGE3_HELPFULNESS = 49.5
STAGE4_HELPFULNESS = 72.9
STAGE5_HELPFULNESS = 90.6

# --- Minimum-evidence gate (ADR-014) ---
# A score cannot enforce a sample-size floor: a perfect 5-vote record legitimately
# out-scores a mediocre 40-vote one, so a lowered threshold alone re-admits the
# small-sample exploit. Stages additionally require vote *volume*.
MIN_VOTES_PER_VERIFIED_REVIEW = 4
STAGE_MIN_VERIFIED_REVIEWS = {3: 5, 4: 15, 5: 50}


def reputation_score(
    helpfulness_ratio: float,
    verified_review_count: int,
    best_answer_count: int,
    strikes: int,
) -> float:
    """Deterministic trust score in [0, 100]."""
    helpfulness = W_HELPFULNESS * max(0.0, min(100.0, helpfulness_ratio))
    volume = min(VOLUME_CAP, VOLUME_COEFF * math.log10(1 + max(0, verified_review_count)))
    best_answers = min(BEST_ANSWER_CAP, BEST_ANSWER_COEFF * max(0, best_answer_count))
    raw = helpfulness + volume + best_answers - STRIKE_PENALTY * max(0, strikes)
    return max(0.0, min(100.0, raw))


def helpfulness_score(helpful_votes: int, unhelpful_votes: int) -> float:
    """Confidence-corrected helpfulness in [0, 100] (ADR-014).

    Wilson lower bound rather than `helpful / total`, so a small perfect record
    is not scored as a large one: 1/1 -> 20.65, not 100.0. Runs on the
    denormalized vote counters, keeping `recompute_user_trust` a single cheap
    aggregate rather than a per-vote scan on a write path.
    """
    total = max(0, helpful_votes) + max(0, unhelpful_votes)
    if total <= 0:
        return 0.0
    return round(100.0 * wilson_lower_bound(max(0, helpful_votes), total), 2)


def determine_stage(
    review_count: int,
    verified_review_count: int,
    helpfulness_ratio: float,
    best_answer_count: int,
    strikes: int,
    months_active: float,
) -> int:
    """Highest trust stage the *score* unlocks (FR-7). Returns 0..5.

    Thresholds are ADR-014 values, sized for `helpfulness_score`. This is the
    score ladder only — callers must additionally apply `evidence_capped_stage`
    so that vote volume, not just score, is required to climb.
    """
    if (verified_review_count >= 50 and helpfulness_ratio >= STAGE5_HELPFULNESS
            and months_active >= 6):
        return 5
    if (verified_review_count >= 15 and strikes == 0
            and best_answer_count >= 3 and helpfulness_ratio >= STAGE4_HELPFULNESS):
        return 4
    if verified_review_count >= 5 and helpfulness_ratio >= STAGE3_HELPFULNESS:
        return 3
    if verified_review_count >= 1:
        return 2
    if review_count >= 1:
        return 1
    return 0


def evidence_capped_stage(stage: int, total_votes: int) -> int:
    """Cap a score-derived stage at what the vote evidence supports (ADR-014).

    Stages 3+ require `MIN_VOTES_PER_VERIFIED_REVIEW x` the stage's verified-review
    requirement in community votes. Without this, five arranged up-votes reach
    Stage 3 no matter how the score threshold is tuned. Stages 0-2 are unaffected:
    they gate on posting, not on reception.
    """
    capped = stage
    while capped >= 3:
        required = MIN_VOTES_PER_VERIFIED_REVIEW * STAGE_MIN_VERIFIED_REVIEWS[capped]
        if total_votes >= required:
            break
        capped -= 1
    return capped


def gate_vote_weight(
    trust_stage: int,
    reputation_score_value: float,
    account_age_days: int,
    is_on_probation: bool,
) -> float:
    """earn_eligible gate vote weight (FR-7).

    Stage 0 = 0 (no gate voting). Stage 1 = flat 0.25. Stage 2+ = multiplier x
    trust%. Accounts < 30 days: halved. Probation: 0.
    """
    if is_on_probation or trust_stage <= 0:
        return 0.0
    if trust_stage == 1:
        weight = STAGE_MULTIPLIER[1]
    else:
        trust_pct = max(0.0, min(100.0, reputation_score_value)) / 100.0
        weight = STAGE_MULTIPLIER.get(trust_stage, 0.0) * trust_pct
    if account_age_days < ACCOUNT_MATURATION_DAYS:
        weight *= 0.5
    return weight


def honesty_score(trust_weighted_helpful_votes: Decimal, price_php: Decimal) -> Decimal:
    """Honesty Score = trust-weighted helpfulness votes x price-bracket multiplier (FR-6)."""
    return Decimal(trust_weighted_helpful_votes) * honesty_price_multiplier(Decimal(price_php))
