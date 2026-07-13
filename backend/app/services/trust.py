"""Trust progression & incentive math (ADR-003).

Pure functions. `reputation_score` (the spec's undefined "trust score percentage",
A1) is defined here as a deterministic 0-100 blend so gate vote weights are
testable. Weights are pinned and documented in ADR-003.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.core.constants import ACCOUNT_MATURATION_DAYS, honesty_price_multiplier

# --- reputation_score weights (ADR-003); components cap at 100 total ---
W_HELPFULNESS = 0.60          # up to 60 pts from helpfulness ratio (0-100)
VOLUME_CAP = 25.0             # up to 25 pts from verified-review volume
VOLUME_COEFF = 10.0           # 10 * log10(1 + n)
BEST_ANSWER_CAP = 15.0        # up to 15 pts from Best Answers
BEST_ANSWER_COEFF = 3.0
STRIKE_PENALTY = 15.0         # per strike

# --- Gate vote-weight multipliers per trust stage (FR-7) ---
STAGE_MULTIPLIER = {0: 0.0, 1: 0.25, 2: 1.0, 3: 1.5, 4: 2.0, 5: 3.0}


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


def determine_stage(
    review_count: int,
    verified_review_count: int,
    helpfulness_ratio: float,
    best_answer_count: int,
    strikes: int,
    months_active: float,
) -> int:
    """Highest unlocked trust stage (FR-7). Returns 0..5."""
    if (verified_review_count >= 50 and helpfulness_ratio >= 90 and months_active >= 6):
        return 5
    if (verified_review_count >= 15 and strikes == 0
            and best_answer_count >= 3 and helpfulness_ratio >= 80):
        return 4
    if verified_review_count >= 5 and helpfulness_ratio >= 70:
        return 3
    if verified_review_count >= 1:
        return 2
    if review_count >= 1:
        return 1
    return 0


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
