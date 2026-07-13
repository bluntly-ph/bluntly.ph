# ADR-003: `reputation_score` (trust %) formula

- **Status:** Accepted (M0)
- **Context (PRD A1, Architecture §8 Q4):** The "trust score percentage" multiplies
  gate vote weights but has no defined formula. It must be deterministic and
  testable before trust progression is built.

## Decision
`reputation_score ∈ [0, 100]`, a deterministic blend (implemented in
`app/services/trust.py::reputation_score`, unit-tested in `tests/test_trust.py`):

| Component | Formula | Cap |
|---|---|---|
| Helpfulness | `0.60 × helpfulness_ratio` (ratio 0–100) | 60 |
| Verified-review volume | `10 × log10(1 + verified_review_count)` | 25 |
| Best Answers | `3 × best_answer_count` | 15 |
| Strike penalty | `− 15 × strikes` | — |

`score = clamp(helpfulness + volume + best_answers − penalty, 0, 100)`.

Maxed components sum to exactly 100. Recency/decay of the *inputs* (e.g.
helpfulness_ratio) is handled upstream by the vote decay in ADR-004; the score
itself is a pure function of current aggregates, so it is trivially recomputable
and testable.

## Trust-stage vote weights (FR-7)
`gate_vote_weight` = stage multiplier × trust% (Stage 2+), flat 0.25 (Stage 1),
0 (Stage 0 / probation); halved for accounts < 30 days. Multipliers:
`{0:0, 1:0.25, 2:1.0, 3:1.5, 4:2.0, 5:3.0}`.

## Consequences
Weights are a starting calibration; they are centralised constants and can be
re-tuned with the accompanying tests as evaluation data arrives.
