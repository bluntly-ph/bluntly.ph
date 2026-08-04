"""Deterrence Delta (Δd) — recovering a prevented purchase from funnel data.

PROPOSAL EVIDENCE, NOT SHIPPED BEHAVIOUR. Nothing in `app/` calls this. It exists
so the estimator proposed for the Honesty Fund's missing "frequency" term can be
checked against known ground truth before any money is wired to it. See
`docs/2026-08-03-algorithm-decisions.md` §A3.

The problem: a negative review prevents purchases, and the reviewer should be paid
the commission they would have earned. The prevented purchase is counterfactual —
no sale, no event to log.

The move: a session arriving on a product page has already declared purchase
intent (PRD §2: "punta, basa, bili"). Sessions reading only POSITIVE reviews of
that product are a contemporaneous control group for sessions reading NEGATIVE
review i. The conversion gap between the two arms is the deterrence effect.

    r₊  = clicks/views, control arm      (estimates θ)
    rᵢ  = clicks/views, treated arm      (estimates θ·(1 − dᵢ))
    Δdᵢ = max(0, (r₊ − rᵢ) − z·SE)       SE = √(r₊(1−r₊)/n₊ + rᵢ(1−rᵢ)/nᵢ)
    Dᵢ  = Vᵢ · Δdᵢ                       deterred purchases

Because both arms are drawn from the same product in the same window, seasonal
demand cancels out of the subtraction — which is why this needs no trend model.

Pure and deterministic: fixed-seed `random.Random(SEED)`, no clock, no database.
`z` is `ranking.WILSON_Z_95`, the constant already pinned by ADR-004.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from app.services.ranking import WILSON_Z_95

SEED = 42
THETA = 0.10  # baseline conversion of an intent-bearing session
REPS = 400    # trials averaged per reported cell


@dataclass(frozen=True)
class Estimate:
    """One (true_deterrence, sample size) cell of a sweep."""

    true_deterrence: float
    sessions_per_arm: int
    truth: float
    point: float
    conservative: float


def deterrence_delta(clicks_c: int, views_c: int, clicks_t: int, views_t: int,
                     *, conservative: bool = True) -> float:
    """Control conversion minus treated conversion, floored at zero.

    `conservative` subtracts the two-proportion 95% CI margin so the estimator
    underpays rather than overpays — the correct bias direction for a payout.
    """
    if views_c <= 0 or views_t <= 0:
        return 0.0
    r_c = clicks_c / views_c
    r_t = clicks_t / views_t
    diff = r_c - r_t
    if conservative:
        se = math.sqrt(r_c * (1 - r_c) / views_c + r_t * (1 - r_t) / views_t)
        diff -= WILSON_Z_95 * se
    return max(0.0, diff)


def _arm(n: int, p: float, rng: random.Random) -> int:
    """n intent-bearing sessions, each clicking through with probability p."""
    return sum(1 for _ in range(n) if rng.random() < p)


def estimate(true_deterrence: float, sessions_per_arm: int, *,
             conservative: bool, reps: int = REPS) -> float:
    """Mean estimated deterred-purchase count over `reps` seeded trials."""
    rng = random.Random(SEED)
    total = 0.0
    for _ in range(reps):
        clicks_c = _arm(sessions_per_arm, THETA, rng)
        clicks_t = _arm(sessions_per_arm, THETA * (1 - true_deterrence), rng)
        total += sessions_per_arm * deterrence_delta(
            clicks_c, sessions_per_arm, clicks_t, sessions_per_arm,
            conservative=conservative)
    return total / reps


def sweep(true_deterrences: tuple[float, ...], sessions_per_arm: int) -> list[Estimate]:
    """Point vs conservative estimates against ground truth."""
    return [
        Estimate(
            true_deterrence=d,
            sessions_per_arm=sessions_per_arm,
            truth=sessions_per_arm * THETA * d,
            point=estimate(d, sessions_per_arm, conservative=False),
            conservative=estimate(d, sessions_per_arm, conservative=True),
        )
        for d in true_deterrences
    ]


def view_inflation_attack(bot_views: int, *, sessions: int = 1000,
                          true_deterrence: float = 0.20) -> float:
    """Mean estimated D when `bot_views` non-clicking views are injected.

    Bot views raise Vᵢ AND depress rᵢ, and D = V·Δd multiplies both — so the
    gain is superlinear. Mitigation is to count only qualified sessions
    (authenticated, aged >= ACCOUNT_MATURATION_DAYS, one per user per product
    per cycle), which keeps bots out of Vᵢ entirely: pass bot_views=0.
    """
    rng = random.Random(SEED)
    total = 0.0
    for _ in range(REPS):
        clicks_c = _arm(sessions, THETA, rng)
        clicks_t = _arm(sessions, THETA * (1 - true_deterrence), rng)
        total += (sessions + bot_views) * deterrence_delta(
            clicks_c, sessions, clicks_t, sessions + bot_views, conservative=False)
    return total / REPS


def main() -> None:
    print("1. UNBIASEDNESS (5,000 sessions/arm)")
    print(f"{'true d':>7} {'truth':>8} {'point':>9} {'conservative':>13}")
    for e in sweep((0.0, 0.10, 0.30, 0.60), 5000):
        print(f"{e.true_deterrence:>7.2f} {e.truth:>8.1f} {e.point:>9.1f} "
              f"{e.conservative:>13.1f}")

    print("\n2. SMALL-n SAFETY (conservative)")
    print(f"{'n/arm':>7} {'d=0':>8} {'d=0.30':>9} {'truth':>8}")
    for n in (30, 500, 2000, 10000):
        noise = estimate(0.0, n, conservative=True)
        real = estimate(0.30, n, conservative=True)
        print(f"{n:>7} {noise:>8.2f} {real:>9.1f} {n * THETA * 0.30:>8.1f}")

    print("\n3. VIEW-INFLATION ATTACK (truth = 20.0)")
    truth = 1000 * THETA * 0.20
    for bots in (0, 250, 1000, 4000):
        d = view_inflation_attack(bots)
        label = "honest" if bots == 0 else f"+{bots} bot views"
        print(f"  {label:<18} D = {d:>6.1f}   {d / truth:>5.1f}x truth")
    print("  qualified-session filter keeps bots out of V -> back to 1.0x")


if __name__ == "__main__":
    main()
