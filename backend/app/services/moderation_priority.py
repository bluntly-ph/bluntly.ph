"""Canonical, explainable review-priority policy (design §5).

This module is pure: it takes already-loaded facts and returns an assessment.
It never queries a database, never mutates content/trust/votes/funds, and
never imports reading telemetry (design §1, §11; enforced by
``tests/test_telemetry_isolation.py``). Reading time, scroll depth,
interaction timing, geography, Wilson score, reputation, trust stage,
verification status, and star rating are not inputs and contribute zero.

Later slices (queue batching, persistence, UI) consume ``evaluate_priority``
without re-implementing any of this scoring.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import ModerationReason

POLICY_VERSION = "review-priority-v1"


class PriorityLane(str, enum.Enum):
    """Mutually exclusive operational routing, in precedence order."""

    escalated = "escalated"
    reported = "reported"
    integrity = "integrity"
    routine = "routine"
    # Separate second-review sampling of completed decisions (design §8).
    # Never assigned by this review-submission evaluator.
    quality_audit = "quality_audit"


class PriorityBand(str, enum.Enum):
    high = "high"
    normal = "normal"
    low = "low"


class SlaState(str, enum.Enum):
    on_track = "on_track"
    approaching = "approaching"
    overdue = "overdue"


@dataclass(frozen=True)
class PriorityFacts:
    """Already-loaded inputs for one queue candidate. No PII, no telemetry."""

    queued_at: datetime
    report_count: int
    report_reasons: frozenset[ModerationReason]
    edited_since_monetized: bool
    velocity: bool
    collusion: bool
    duplicate_content: bool
    manually_escalated: bool = False


@dataclass(frozen=True)
class PriorityFactor:
    code: str
    observed: bool | int | str
    contribution: int
    explanation: str


@dataclass(frozen=True)
class PriorityAssessment:
    policy_version: str
    lane: PriorityLane
    integrity_score: int
    band: PriorityBand
    sla_state: SlaState
    due_at: datetime
    factors: tuple[PriorityFactor, ...]
    order_key: tuple[int, int, int, datetime, datetime]


# --------------------------------------------------------------------------- #
# Policy constants (design §5)
# --------------------------------------------------------------------------- #

_SCORE_CAP = 100
_HIGH_SCORE_THRESHOLD = 40
_NORMAL_SCORE_THRESHOLD = 15
_APPROACHING_FRACTION = 0.75

_SLA_TARGETS: dict[PriorityLane, timedelta] = {
    PriorityLane.escalated: timedelta(hours=1),
    PriorityLane.reported: timedelta(hours=4),
    PriorityLane.integrity: timedelta(hours=8),
    PriorityLane.routine: timedelta(hours=24),
    PriorityLane.quality_audit: timedelta(hours=72),
}

_LANE_RANK: dict[PriorityLane, int] = {
    PriorityLane.escalated: 0,
    PriorityLane.reported: 1,
    PriorityLane.integrity: 2,
    PriorityLane.routine: 3,
    PriorityLane.quality_audit: 4,
}

_SLA_RANK: dict[SlaState, int] = {
    SlaState.overdue: 0,
    SlaState.approaching: 1,
    SlaState.on_track: 2,
}

# Highest count bracket first: only the highest-count bracket applies
# (design §5.1 — prevents report brigading from growing the score unbounded).
_REPORT_COUNT_BRACKETS: tuple[tuple[int, str, int], ...] = (
    (4, "report_count_4_plus", 35),
    (2, "report_count_2_3", 25),
    (1, "report_count_1", 15),
)

# Highest tier first: only the highest-tier report reason applies, regardless
# of how many reports carry it (design §5.1).
_REPORT_REASON_TIERS: tuple[tuple[int, tuple[ModerationReason, ...]], ...] = (
    (20, (ModerationReason.fake_proof, ModerationReason.harassment)),
    (15, (ModerationReason.seller_posing_as_buyer, ModerationReason.plagiarized)),
    (10, (ModerationReason.conflict_of_interest,)),
    (5, (ModerationReason.spam,)),
    (0, (ModerationReason.other,)),
)

_REPORT_REASON_LABELS: dict[ModerationReason, str] = {
    ModerationReason.fake_proof: "fake proof of purchase",
    ModerationReason.harassment: "harassment",
    ModerationReason.seller_posing_as_buyer: "a seller posing as a buyer",
    ModerationReason.plagiarized: "plagiarized content",
    ModerationReason.conflict_of_interest: "an undisclosed conflict of interest",
    ModerationReason.spam: "spam",
    ModerationReason.other: "an unspecified concern",
}


def _require_aware_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _report_count_factor(report_count: int) -> PriorityFactor | None:
    for threshold, code, contribution in _REPORT_COUNT_BRACKETS:
        if report_count >= threshold:
            if threshold == 1:
                explanation = "One person reported this review."
            else:
                explanation = f"{report_count} distinct people reported this review."
            return PriorityFactor(
                code=code, observed=report_count,
                contribution=contribution, explanation=explanation,
            )
    return None


def _report_reason_factor(
    report_reasons: frozenset[ModerationReason],
) -> PriorityFactor | None:
    if not report_reasons:
        return None
    for contribution, reasons in _REPORT_REASON_TIERS:
        winner = next((reason for reason in reasons if reason in report_reasons), None)
        if winner is not None:
            return PriorityFactor(
                code=f"report_reason_{winner.value}",
                observed=winner.value,
                contribution=contribution,
                explanation=(
                    f"The most serious report reason is {_REPORT_REASON_LABELS[winner]}."
                ),
            )
    return None


def _lane_for(facts: PriorityFacts) -> PriorityLane:
    if facts.manually_escalated:
        return PriorityLane.escalated
    if facts.report_count > 0:
        return PriorityLane.reported
    if facts.edited_since_monetized or facts.velocity or facts.collusion or facts.duplicate_content:
        return PriorityLane.integrity
    return PriorityLane.routine


def _sla_state_for(*, elapsed: timedelta, target: timedelta) -> SlaState:
    if elapsed >= target:
        return SlaState.overdue
    if elapsed >= target * _APPROACHING_FRACTION:
        return SlaState.approaching
    return SlaState.on_track


def _band_for(*, lane: PriorityLane, sla_state: SlaState, integrity_score: int) -> PriorityBand:
    if lane is PriorityLane.escalated or sla_state is SlaState.overdue \
            or integrity_score >= _HIGH_SCORE_THRESHOLD:
        return PriorityBand.high
    if sla_state is SlaState.approaching or integrity_score >= _NORMAL_SCORE_THRESHOLD:
        return PriorityBand.normal
    return PriorityBand.low


def evaluate_priority(facts: PriorityFacts, *, now: datetime) -> PriorityAssessment:
    """Evaluate one already-loaded candidate against policy v1.

    Raises ``ValueError`` if ``facts.queued_at`` or ``now`` is a naive
    datetime — SLA math must never silently assume a timezone.
    """
    _require_aware_utc(facts.queued_at, "facts.queued_at")
    _require_aware_utc(now, "now")

    factors: list[PriorityFactor] = []
    if facts.edited_since_monetized:
        factors.append(PriorityFactor(
            code="edited_after_monetization", observed=True, contribution=40,
            explanation="The review was edited after its product started earning commission.",
        ))
    if facts.collusion:
        factors.append(PriorityFactor(
            code="collusion", observed=True, contribution=35,
            explanation="A voting-collusion advisory fired for this review.",
        ))
    if facts.duplicate_content:
        factors.append(PriorityFactor(
            code="duplicate_content", observed=True, contribution=30,
            explanation="The review body closely matches another review.",
        ))
    if facts.velocity:
        factors.append(PriorityFactor(
            code="vote_velocity", observed=True, contribution=15,
            explanation="An unusual vote-velocity advisory fired for this review.",
        ))
    report_count_factor = _report_count_factor(facts.report_count)
    if report_count_factor is not None:
        factors.append(report_count_factor)
    report_reason_factor = _report_reason_factor(facts.report_reasons)
    if report_reason_factor is not None:
        factors.append(report_reason_factor)

    integrity_score = min(_SCORE_CAP, sum(factor.contribution for factor in factors))

    lane = _lane_for(facts)
    target = _SLA_TARGETS[lane]
    due_at = facts.queued_at + target
    sla_state = _sla_state_for(elapsed=now - facts.queued_at, target=target)
    band = _band_for(lane=lane, sla_state=sla_state, integrity_score=integrity_score)

    order_key = (
        _LANE_RANK[lane],
        _SLA_RANK[sla_state],
        -integrity_score,
        due_at,
        facts.queued_at,
    )

    return PriorityAssessment(
        policy_version=POLICY_VERSION,
        lane=lane,
        integrity_score=integrity_score,
        band=band,
        sla_state=sla_state,
        due_at=due_at,
        factors=tuple(factors),
        order_key=order_key,
    )
