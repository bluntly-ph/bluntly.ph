# ADR-014: Helpfulness estimator + minimum-evidence gate

- **Status:** **Accepted / implemented** (2026-08-04). Amends ADR-003 (the
  `helpfulness_ratio` input) and the FR-7 stage thresholds.
- **Context:** `trust_service.recompute_user_trust` computes
  `helpfulness = 100 × helpful / (helpful + unhelpful)` — a raw proportion with no
  confidence correction. One up-vote and zero down-votes scores 100.0. That value is
  60% of `reputation_score` (ADR-003), which gates `determine_stage`, which sets
  `gate_vote_weight`, which weights the earn-eligible gate that pays the Honesty
  Fund. Five arranged votes therefore buy a full-strength vote on a money path.

  Measured on the shipped functions: a 5-review/5-vote account scores **67.78**
  reputation against **64.22** for a reviewer with 100 votes at 85% helpful — the
  fabricated record outranks the real one.

## Decision
Two changes, landed together. Either alone is insufficient (see Consequences).

| Change | From | To | Symbol |
|---|---|---|---|
| Helpfulness estimator | `helpful / total` | Wilson lower bound on the same counts | `trust.helpfulness_score` |
| Stage 3/4/5 score thresholds | 70 / 80 / 90 | 49.5 / 72.9 / 90.6 | `STAGE{3,4,5}_HELPFULNESS` |
| Minimum-evidence gate | *(none)* | 4 × the stage's verified-review requirement (20 / 60 / 200 votes) | `trust.evidence_capped_stage` |

**Estimator choice — plain Wilson, not time-decayed.** The proposal called for
`time_decayed_wilson`. Implementation uses `wilson_lower_bound` on the
denormalized `helpful_votes` / `unhelpful_votes` counters instead. Decay would
require loading every individual `review_votes` row for the author inside
`recompute_user_trust`, which runs on **every vote write** — turning one cheap
aggregate into a per-vote scan on a hot path. Decay addresses staleness; the
defect here is small-sample inflation, which plain Wilson fixes on its own. If
recency becomes a problem, revisit with a materialized decay column.

**Composition, not signature change.** `determine_stage` keeps its ADR-003
signature and stays the pure score ladder — the capstone notebook calls it and
`inspect.getsource`s it. The gate is a separate function the caller composes:
`evidence_capped_stage(determine_stage(...), total_votes)`. A defaulted extra
parameter was rejected as a silent footgun (a caller omitting it would demote
every user to Stage 2).

Thresholds are placeholders from a modelled cohort (10th percentile, 8
votes/review) and shift materially with that assumption — Stage 3 lands at
38.7 / 49.5 / 57.9 for 4 / 8 / 16 votes per review. Re-tune from real vote data.

## Consequences
- **The estimator alone does not close the exploit.** Because a lower bound is
  stricter than a proportion, thresholds must drop to preserve honest progression —
  and at the lowered thresholds the 5-vote account still scores above the bar
  (56.6 vs 49.5 at Stage 3). Wilson correctly reports that a perfect small record is
  good evidence; it cannot also enforce a sample-size floor. Hence the gate.
- **The gate raises attacker cost ~4×, it does not eliminate the attack**
  (5 → 20 arranged votes for Stage 3). An attacker with enough distinct qualified
  voters still climbs; the residual is the job of the velocity and reciprocity
  signals in ADR-004, and of ring detection if that is built.
- **Existing users' scores move on next recompute.** `helpfulness_ratio` is
  recomputed on any vote write, publish, or the periodic sweep — no backfill
  migration is needed, but a user's displayed score will drop the first time it
  recomputes (85.0 → 76.72 for a 85/100 record). Expect support questions.
- **Capstone material moves.** The notebook's `reputation_score.png` and
  trust-ladder cells re-render from live source, so they pick the change up on
  re-run — but the numbers a panel sees will differ from any pre-printed copy.
- Verified: 3 integration tests updated to assert against `helpfulness_score`
  rather than the old literal `100.0`; 3 new unit tests cover the small-sample
  discount, the blocked exploit, and the gate's stepwise cap.
- Evidence: `backend/sim/helpfulness_estimator.py` (`python -m sim.helpfulness_estimator`).
  Seeded, pure, imports the shipped functions; nothing in `app/` imports it.
- Defense material: notebook **§2.3** (`docs/notebooks/bluntly-algorithms.ipynb`) demonstrates
  both halves live — the small-sample discount curve and the before/after gate weights — and
  §2.2's stage table carries the re-derived thresholds plus the minimum-vote column. The
  notebook imports the real functions, so those figures cannot drift from the code.
