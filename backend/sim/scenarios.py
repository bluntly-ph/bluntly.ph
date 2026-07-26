"""Vote-influx scenarios driven through the real ranking math (ADR-004).

Pure and deterministic: no wall clock, no database, no randomness beyond a
fixed-seed `random.Random(SEED)`. Every vote carries the absolute simulation day
it was cast on, and scores are always evaluated at an explicit observation time,
matching `app.services.ranking`'s pure-function contract.

Four scenarios, each returning a plain dataclass the charts and the tests share:
  S1 small-n vs large-n        -> why Wilson instead of a naive percentage
  S2 brigade burst             -> 200 upvotes in 10 minutes
  S3 decay handover            -> a frozen champion losing to a steady challenger
  S4 downvote raid             -> 150 downvotes in 10 minutes
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.services.ranking import (
    DECAY_HALF_LIFE_DAYS,
    GATE_WILSON_LB,
    VELOCITY_THRESHOLD,
    VELOCITY_WINDOW_SECONDS,
    decay_factor,
    time_decayed_wilson,
    velocity_exceeded,
    wilson_lower_bound,
)

SEED = 42
MINUTE = 1.0 / 1440.0  # one minute expressed in days
HOMEPAGE_SLOTS = 6  # lib/reviews.ts:229 -> /reviews/feed?sort=wilson&limit=6

# A vote is (is_positive, cast_on_day). Ages are derived at observation time.
Vote = tuple[bool, float]


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------
def score_at(votes: list[Vote], now_day: float) -> float:
    """Time-decayed Wilson lower bound over the votes cast on or before `now_day`."""
    return time_decayed_wilson(
        (is_positive, now_day - cast) for is_positive, cast in votes if cast <= now_day
    )


def effective_n_at(votes: list[Vote], now_day: float) -> float:
    """Sum of decay weights — the 'effective n' ADR-004 runs the gate on."""
    return sum(
        decay_factor(now_day - cast) for _, cast in votes if cast <= now_day
    )


def velocity_at(votes: list[Vote], now_day: float) -> bool:
    """`velocity_exceeded` over up-votes only, mirroring fraud_service._velocity_flag.

    fraud_service.py:41 filters `vote == VoteDirection.up`, so down-votes are
    invisible to this signal at any volume (finding F2).
    """
    ages_seconds = [
        (now_day - cast) * 86400.0
        for is_positive, cast in votes
        if is_positive and cast <= now_day
    ]
    return velocity_exceeded(ages_seconds)


def upvotes_in_last_hour(votes: list[Vote], now_day: float) -> int:
    """Raw count for the chart's second panel — what the threshold is compared against."""
    window_days = VELOCITY_WINDOW_SECONDS / 86400.0
    return sum(
        1
        for is_positive, cast in votes
        if is_positive and now_day - window_days < cast <= now_day
    )


def spread_votes(
    rng: random.Random, count: int, positive_rate: float,
    start_day: float, end_day: float,
) -> list[Vote]:
    """`count` votes scattered over [start_day, end_day] at the given positive rate.

    Positivity is assigned by exact count (not per-vote coin flips) so the rate is
    reproduced precisely at any n, then shuffled so it is not time-correlated.
    """
    positives = round(count * positive_rate)
    flags = [True] * positives + [False] * (count - positives)
    rng.shuffle(flags)
    if count == 1:
        days = [start_day]
    else:
        step = (end_day - start_day) / (count - 1)
        days = [start_day + i * step for i in range(count)]
    return list(zip(flags, days, strict=True))


def burst_votes(count: int, *, positive: bool, start_day: float,
                minutes: float) -> list[Vote]:
    """`count` identical votes packed evenly into a `minutes`-long window."""
    span = minutes * MINUTE
    step = span / max(1, count - 1)
    return [(positive, start_day + i * step) for i in range(count)]


# --------------------------------------------------------------------------
# S1 — small-n vs large-n
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SmallNResult:
    """Naive proportion against Wilson lower bound as the sample grows."""

    counts: list[int]
    naive: dict[str, list[float]]
    wilson: dict[str, list[float]]
    max_n: int

    def wilson_at(self, label: str, n: int) -> float:
        return self.wilson[label][self.counts.index(n)]


def small_n_vs_large_n(max_n: int = 200) -> SmallNResult:
    """Sweep n at fixed positive rates. No time involved — undecayed Wilson."""
    counts = list(range(1, max_n + 1))
    rates = {"100% positive": 1.00, "95% positive": 0.95}
    naive: dict[str, list[float]] = {}
    wilson: dict[str, list[float]] = {}
    for label, rate in rates.items():
        naive[label] = []
        wilson[label] = []
        for n in counts:
            positives = round(n * rate)
            naive[label].append(positives / n)
            wilson[label].append(wilson_lower_bound(positives, n))
    return SmallNResult(counts=counts, naive=naive, wilson=wilson, max_n=max_n)


# --------------------------------------------------------------------------
# Shared: a synthetic homepage field to rank against
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldReview:
    name: str
    votes: list[Vote]


def homepage_field(rng: random.Random, *, as_of_day: float,
                   size: int = 9) -> list[FieldReview]:
    """Organic reviews standing in for the rest of the feed.

    Vote counts and positive rates fan out so the field has a realistic spread of
    scores; the 6th-best of these is the homepage cut-off a challenger must beat.
    """
    field_reviews = []
    for i in range(size):
        count = 8 + i * 9              # 8, 17, 26, ... 80
        rate = 0.70 + 0.03 * (i % 6)   # 0.70 .. 0.85
        age_span = 12.0 + 4.0 * (i % 5)
        field_reviews.append(FieldReview(
            name=f"organic-{i + 1}",
            votes=spread_votes(rng, count, rate,
                               start_day=max(0.0, as_of_day - age_span),
                               end_day=as_of_day - 0.5),
        ))
    return field_reviews


def homepage_cutoff(field_reviews: list[FieldReview], now_day: float) -> float:
    """Score of the review sitting in the last homepage slot."""
    scores = sorted((score_at(r.votes, now_day) for r in field_reviews), reverse=True)
    idx = min(HOMEPAGE_SLOTS - 1, len(scores) - 1)
    return scores[idx]


def rank_among(field_reviews: list[FieldReview], subject: list[Vote],
               now_day: float) -> int:
    """1-based rank of `subject` if it were inserted into the field."""
    subject_score = score_at(subject, now_day)
    better = sum(1 for r in field_reviews if score_at(r.votes, now_day) > subject_score)
    return better + 1


# --------------------------------------------------------------------------
# S2 — brigade burst
# --------------------------------------------------------------------------
@dataclass
class BurstResult:
    """Per-minute trajectory of a brigaded review against an organic control."""

    minutes: list[float] = field(default_factory=list)
    target_score: list[float] = field(default_factory=list)
    control_score: list[float] = field(default_factory=list)
    cutoff: list[float] = field(default_factory=list)
    target_rank: list[int] = field(default_factory=list)
    hourly_upvotes: list[int] = field(default_factory=list)
    velocity_flag: list[bool] = field(default_factory=list)
    burst_minutes: float = 0.0
    burst_size: int = 0
    target_votes: list[Vote] = field(default_factory=list)
    control_votes: list[Vote] = field(default_factory=list)

    @property
    def first_flag_minute(self) -> float | None:
        for m, flag in zip(self.minutes, self.velocity_flag, strict=True):
            if flag:
                return m
        return None

    @property
    def minute_entering_homepage(self) -> float | None:
        for m, rank in zip(self.minutes, self.target_rank, strict=True):
            if rank <= HOMEPAGE_SLOTS:
                return m
        return None


def brigade_burst(burst_size: int = 200, burst_minutes: float = 10.0,
                  event_day: float = 30.0) -> BurstResult:
    """200 up-votes inside 10 minutes on a review with a thin organic history."""
    rng = random.Random(SEED)
    control = spread_votes(rng, 40, 0.85, start_day=0.0, end_day=event_day - 0.5)
    target = spread_votes(rng, 12, 0.85, start_day=0.0, end_day=20.0)
    target += burst_votes(burst_size, positive=True,
                          start_day=event_day, minutes=burst_minutes)
    field_reviews = homepage_field(rng, as_of_day=event_day)

    result = BurstResult(burst_minutes=burst_minutes, burst_size=burst_size,
                         target_votes=target, control_votes=control)
    for step in range(-5, 61):
        now = event_day + step * MINUTE
        result.minutes.append(float(step))
        result.target_score.append(score_at(target, now))
        result.control_score.append(score_at(control, now))
        result.cutoff.append(homepage_cutoff(field_reviews, now))
        result.target_rank.append(rank_among(field_reviews, target, now))
        result.hourly_upvotes.append(upvotes_in_last_hour(target, now))
        result.velocity_flag.append(velocity_at(target, now))
    return result


# --------------------------------------------------------------------------
# S3 — decay handover
# --------------------------------------------------------------------------
@dataclass
class DecayResult:
    """A champion frozen on day 0 versus a challenger voted on every day."""

    days: list[int] = field(default_factory=list)
    champion_score: list[float] = field(default_factory=list)
    challenger_score: list[float] = field(default_factory=list)
    champion_effective_n: list[float] = field(default_factory=list)
    challenger_effective_n: list[float] = field(default_factory=list)
    champion_votes: list[Vote] = field(default_factory=list)
    challenger_votes: list[Vote] = field(default_factory=list)

    @property
    def crossover_day(self) -> int | None:
        for day, champ, chall in zip(self.days, self.champion_score,
                                     self.challenger_score, strict=True):
            if chall > champ:
                return day
        return None


def decay_handover(horizon_days: int = 120, champion_votes_count: int = 100,
                   positive_rate: float = 0.95) -> DecayResult:
    """Both reviews sit at the same positive rate, so only effective n separates them."""
    rng = random.Random(SEED)
    champion = spread_votes(rng, champion_votes_count, positive_rate,
                            start_day=0.0, end_day=0.0)
    challenger = spread_votes(rng, horizon_days + 1, positive_rate,
                              start_day=0.0, end_day=float(horizon_days))

    result = DecayResult(champion_votes=champion, challenger_votes=challenger)
    for day in range(horizon_days + 1):
        now = float(day)
        result.days.append(day)
        result.champion_score.append(score_at(champion, now))
        result.challenger_score.append(score_at(challenger, now))
        result.champion_effective_n.append(effective_n_at(champion, now))
        result.challenger_effective_n.append(effective_n_at(challenger, now))
    return result


# --------------------------------------------------------------------------
# S4 — downvote raid
# --------------------------------------------------------------------------
@dataclass
class RaidResult:
    """A healthy review buried by a coordinated down-vote raid."""

    minutes: list[float] = field(default_factory=list)
    score: list[float] = field(default_factory=list)
    cutoff: list[float] = field(default_factory=list)
    rank: list[int] = field(default_factory=list)
    velocity_flag: list[bool] = field(default_factory=list)
    hourly_downvotes: list[int] = field(default_factory=list)
    raid_size: int = 0
    raid_minutes: float = 0.0
    votes: list[Vote] = field(default_factory=list)

    @property
    def score_before(self) -> float:
        return self.score[0]

    @property
    def score_after(self) -> float:
        return self.score[-1]

    @property
    def minute_below_gate(self) -> float | None:
        for m, s in zip(self.minutes, self.score, strict=True):
            if s < GATE_WILSON_LB:
                return m
        return None

    @property
    def minute_leaving_homepage(self) -> float | None:
        for m, rank in zip(self.minutes, self.rank, strict=True):
            if rank > HOMEPAGE_SLOTS:
                return m
        return None

    @property
    def any_velocity_flag(self) -> bool:
        return any(self.velocity_flag)

    @property
    def raid_peak_hourly_downvotes_exceeds_threshold(self) -> bool:
        """The raid volume would trip VELOCITY_THRESHOLD if down-votes counted."""
        return max(self.hourly_downvotes) > VELOCITY_THRESHOLD


def downvote_raid(raid_size: int = 150, raid_minutes: float = 10.0,
                  event_day: float = 30.0) -> RaidResult:
    """150 down-votes in 10 minutes on an 80-up / 5-down review."""
    rng = random.Random(SEED)
    good = spread_votes(rng, 85, 80 / 85, start_day=0.0, end_day=event_day - 0.5)
    votes = good + burst_votes(raid_size, positive=False,
                               start_day=event_day, minutes=raid_minutes)
    field_reviews = homepage_field(rng, as_of_day=event_day)

    result = RaidResult(raid_size=raid_size, raid_minutes=raid_minutes, votes=votes)
    window_days = VELOCITY_WINDOW_SECONDS / 86400.0
    for step in range(-5, 61):
        now = event_day + step * MINUTE
        result.minutes.append(float(step))
        result.score.append(score_at(votes, now))
        result.cutoff.append(homepage_cutoff(field_reviews, now))
        result.rank.append(rank_among(field_reviews, votes, now))
        result.velocity_flag.append(velocity_at(votes, now))
        result.hourly_downvotes.append(sum(
            1 for is_positive, cast in votes
            if not is_positive and now - window_days < cast <= now))
    return result


# --------------------------------------------------------------------------
# Summary tables (shared by __main__ and the doc)
# --------------------------------------------------------------------------
def summary_rows() -> dict[str, list[dict[str, object]]]:
    """Tidy rows per scenario, ready for CSV or a markdown table."""
    s1 = small_n_vs_large_n()
    s2 = brigade_burst()
    s3 = decay_handover()
    s4 = downvote_raid()

    return {
        "s1_small_n": [
            {"votes": n,
             "naive_100pct": round(s1.naive["100% positive"][i], 4),
             "wilson_100pct": round(s1.wilson["100% positive"][i], 4),
             "naive_95pct": round(s1.naive["95% positive"][i], 4),
             "wilson_95pct": round(s1.wilson["95% positive"][i], 4)}
            for i, n in enumerate(s1.counts)
        ],
        "s2_brigade": [
            {"minute": m, "target_wilson": round(t, 4),
             "control_wilson": round(c, 4), "homepage_cutoff": round(cut, 4),
             "target_rank": r, "upvotes_last_hour": u, "velocity_flag": v}
            for m, t, c, cut, r, u, v in zip(
                s2.minutes, s2.target_score, s2.control_score, s2.cutoff,
                s2.target_rank, s2.hourly_upvotes, s2.velocity_flag, strict=True)
        ],
        "s3_decay": [
            {"day": d, "champion_wilson": round(a, 4),
             "challenger_wilson": round(b, 4),
             "champion_effective_n": round(en_a, 3),
             "challenger_effective_n": round(en_b, 3)}
            for d, a, b, en_a, en_b in zip(
                s3.days, s3.champion_score, s3.challenger_score,
                s3.champion_effective_n, s3.challenger_effective_n, strict=True)
        ],
        "s4_raid": [
            {"minute": m, "wilson": round(s, 4), "homepage_cutoff": round(cut, 4),
             "rank": r, "velocity_flag": v, "downvotes_last_hour": d}
            for m, s, cut, r, v, d in zip(
                s4.minutes, s4.score, s4.cutoff, s4.rank,
                s4.velocity_flag, s4.hourly_downvotes, strict=True)
        ],
    }


def headline_facts() -> dict[str, object]:
    """The numbers the document quotes. Computed, never hardcoded in prose."""
    s2 = brigade_burst()
    s3 = decay_handover()
    s4 = downvote_raid()
    return {
        "wilson_5_of_5": wilson_lower_bound(5, 5),
        "wilson_95_of_100": wilson_lower_bound(95, 100),
        "wilson_1_of_1": wilson_lower_bound(1, 1),
        "wilson_200_of_200": wilson_lower_bound(200, 200),
        "burst_size": s2.burst_size,
        "burst_minutes": s2.burst_minutes,
        "burst_score_before": s2.target_score[0],
        "burst_score_after": s2.target_score[-1],
        "burst_rank_before": s2.target_rank[0],
        "burst_rank_after": s2.target_rank[-1],
        "burst_minute_entering_homepage": s2.minute_entering_homepage,
        "burst_first_flag_minute": s2.first_flag_minute,
        "burst_peak_hourly_upvotes": max(s2.hourly_upvotes),
        "velocity_threshold": VELOCITY_THRESHOLD,
        "decay_crossover_day": s3.crossover_day,
        "decay_half_life_days": DECAY_HALF_LIFE_DAYS,
        "champion_effective_n_day0": s3.champion_effective_n[0],
        "champion_effective_n_final": s3.champion_effective_n[-1],
        "challenger_effective_n_final": s3.challenger_effective_n[-1],
        "raid_size": s4.raid_size,
        "raid_score_before": s4.score_before,
        "raid_score_after": s4.score_after,
        "raid_rank_before": s4.rank[0],
        "raid_rank_after": s4.rank[-1],
        "raid_minute_below_gate": s4.minute_below_gate,
        "raid_any_velocity_flag": s4.any_velocity_flag,
        "raid_peak_hourly_downvotes": max(s4.hourly_downvotes),
        "gate_wilson_lb": GATE_WILSON_LB,
        "homepage_slots": HOMEPAGE_SLOTS,
    }
