# ADR-004: Wilson / time-decay / velocity / reciprocity parameters

- **Status:** Accepted (M0)
- **Context (PRD A2, Architecture §8 Q3):** Rankings and fraud flags are
  unimplementable as prose. Windows, decay half-life, and thresholds must be numbers.

## Decision
Implemented in `app/services/ranking.py` (unit-tested in `tests/test_ranking.py`):

| Parameter | Value | Rationale |
|---|---|---|
| Confidence z | `1.95996` (two-sided 95%) | Matches the spec's "0.65 @ 95%" gate |
| Time-decay | exponential, **half-life = 45 days** | ~1.5 evaluation months; recent votes dominate |
| Velocity flag | **> 10 upvotes / 3600 s** sliding window | Advisory surge signal (fraud layer 5) |
| Reciprocity flag | reciprocal rate **> 0.60** over **≥ 5** shared targets | Collusion signal, minimum sample guards noise |
| Post-Seeding gate | Wilson LB (on *effective n*) **≥ 0.65** AND **≥ 3** Stage-2+ voters | FR-6 |
| Phase transition | **≥ 50** Stage-2+ verified reviewers in the pilot category | PRD §2 |

- **Wilson lower bound** accepts weighted (non-integer) counts so it runs on
  *effective n* (trust-weighted) for the gate and on decayed counts for visibility.
- **Compute placement:** on-read for a single content item's visibility score;
  gate evaluation and phase-transition detection run in the earn_eligible service
  path (M2). All functions are pure and side-effect-free.

## Consequences
Every parameter is a named constant, changeable with its test. These are
launch calibrations to be revisited with real vote-volume data (M4→M5).
