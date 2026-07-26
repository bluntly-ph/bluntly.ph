# Ranking Algorithm Simulation Harness — Design

- **Date:** 2026-07-26
- **Status:** Approved, awaiting implementation plan
- **Relates to:** [ADR-004](../../adr/004-wilson-decay-velocity-reciprocity.md), `backend/app/services/ranking.py`

## Problem

`backend/tests/test_ranking.py` pins static values — `wilson_lower_bound(9, 10) == 0.59585`,
`decay_factor(45) == 0.5`, `is_post_seeding(50) is True`. Every assertion is a single
point evaluation.

Nothing exercises a **vote stream over time**, and nothing proves that a change in
`wilson_score` actually reorders what a visitor sees. The capstone claims the ranking
resists brigading and rewards sustained quality; today those claims rest on unit tests
of isolated arithmetic.

We need a simulation that drives realistic vote influxes through the real scoring code,
shows what happens to the site, and produces graphs suitable for the capstone paper.

## Vote-to-website path (as built)

Establishing what the simulation must reproduce:

| Step | Location |
|---|---|
| Vote written | `vote_service.cast_vote` — rejects votes on unpublished reviews and self-votes |
| Score recomputed in the same transaction | `vote_service.recompute_review_vote_aggregates` → `review.wilson_score` |
| Author trust refreshed | `trust_service.recompute_user_trust` via `_finish_vote_write` |
| Decay re-applied nightly | `vote_service.recompute_all_wilson_scores` |
| Feed ordered | `review_service.py:177` — `ORDER BY wilson_score DESC, created_at DESC` |
| Homepage strip | `lib/reviews.ts:229` — `/api/v1/reviews/feed?sort=wilson&limit=6` |
| Product / seller trust | `trust_rating_service.recompute_product_trust`, `recompute_seller_trust` |

So a vote influx changes **which six reviews the homepage shows**, plus product and
seller trust scores.

## Architecture

Three layers, each independently runnable.

```
backend/sim/
  __init__.py
  scenarios.py   # pure vote-stream generators -> score series. Imports only app.services.ranking
  charts.py      # matplotlib (Agg backend) -> docs/assets/ranking/*.png
  __main__.py    # `python -m sim` regenerates every PNG + CSV and prints summary tables
backend/tests/test_ranking_simulation.py   # asserts every claim the doc makes, plus the e2e
docs/RANKING_SIMULATION.md                 # the write-up with embedded graphs
docs/assets/ranking/*.png
```

`scenarios.py` is the single source of truth. `charts.py` plots its output and
`test_ranking_simulation.py` asserts on that same output, so a committed graph cannot
drift from a passing test. All generators are deterministic (`random.Random(42)`), so
regenerating charts produces byte-identical results and an unrelated commit never shows
image churn.

`sim/` sits beside `app/` and `tests/` at the backend root, which is already on
`sys.path` for the test suite. It is excluded from `[tool.setuptools].packages`
(currently `["app"]`), so it never enters the runtime image.

### Dependency

`matplotlib` is added to **`requirements-dev.txt`** and the `dev` group in
`pyproject.toml` (`dev = ["pytest>=8.3", "ruff>=0.7", "locust>=2.31"]`), which are
documented as mirrors of each other. Runtime deps in `requirements.txt` are untouched,
so the Docker image and Vercel deployment gain nothing.

Charts render with the `Agg` backend — no display required, works headless in CI.

## Scenarios

Each scenario is one function in `scenarios.py` returning a tidy dataset; one chart
function; one or more test assertions; one section in the document.

### S1 — Small-n versus large-n

Sweep `n = 1..200` at fixed true positive rates (100%, 95%). For each n compute naive
`p̂` and `wilson_lower_bound(positive, n)`.

**Chart** `wilson_small_n.png` — x = vote count, y = score, four lines: naive 100%,
Wilson 100%, naive 95%, Wilson 95%. Naive lines are flat; Wilson lines climb.

**Headline** a 5/5 review scores below a 95/100 review, so a fresh review with three
perfect votes cannot seize a homepage slot from an established one. Exact values are
computed at render time, never hardcoded into the prose.

**Asserts** `wilson_lower_bound(5, 5) < wilson_lower_bound(95, 100)`; Wilson is
strictly increasing in n at a fixed positive rate; Wilson never exceeds naive `p̂`.

### S2 — Brigade burst

Review A: organic, 40 votes over 30 days, 85% positive.
Review B: 12 organic votes over 20 days, then **200 upvotes inside a 10-minute window**.

Sample both scores per minute from t−5min to t+60min around the burst.

**Chart** `brigade_burst.png`, two stacked panels — top: score trajectories for A and B
with a dashed line marking the homepage top-6 cutoff; bottom: rolling one-hour upvote
count for B against the `VELOCITY_THRESHOLD = 10` line, shaded where
`velocity_exceeded` returns True.

**Asserts** B finishes above A; `velocity_exceeded(B_upvote_ages)` is True; the same
call on A is False; B's stored score crosses the cutoff within the burst window.

### S3 — Decay handover

Champion: 100 votes (95% positive) all cast on day 0, then no new votes ever.
Challenger: one vote per day (95% positive) from day 0.

Sweep t = 0..120 days, computing `time_decayed_wilson` for both at each step.

The champion's effective n decays as `100 · 0.5^(t/45)`. The challenger's converges
toward `45/ln 2 ≈ 64.9`. They cross near day 60.

**Chart** `decay_handover.png` — both score lines with the crossover annotated, and a
secondary axis showing effective n for each.

**Asserts** a crossover exists and falls inside a documented day window; the champion's
effective n matches the closed form within tolerance; the challenger's effective n
converges toward `45/ln 2`.

**Why it matters for the site** the ordering only changes in production if
`recompute_all_wilson_scores` runs. With no new votes on the champion, nothing triggers
a recompute and the stored `wilson_score` stays frozen at its day-0 value. This scenario
demonstrates that the nightly sweep is load-bearing, not housekeeping.

### S4 — Downvote raid

A well-scored review (80 up / 5 down over 30 days) takes **150 downvotes in 10 minutes**.

**Chart** `downvote_raid.png` — score trajectory crossing below the
`GATE_WILSON_LB = 0.65` line, plus a second panel showing the velocity flag flat at
False for the entire raid.

**Asserts** the post-raid Wilson lower bound falls below `GATE_WILSON_LB`; a
velocity check over the review's upvotes stays False throughout, because
`fraud_service._velocity_flag` filters `vote == VoteDirection.up`.

## Findings to document

Two facts traced from the code while designing this. The simulation's job is to
demonstrate them reproducibly. **Both are documented with recommendations; neither is
fixed in this work.** Fixing them is a separate decision.

### F1 — Velocity and collusion flags are unreachable for voted reviews

`fraud_service.compute_signals` is called from exactly one place: `_queue_item` in
`admin_referral.py:55`. `referral_service.get_queue` returns two lists:

- **pending** — requires `published_at IS NULL` (`referral_service.py:261`)
- **edited** — monetized reviews edited since their referral link was issued; these
  *are* published

`vote_service._votable_or_404` raises 404 unless `published_at IS NOT NULL`. A pending
review therefore cannot hold a single vote, so every pending queue card reports
`velocity: false` and `collusion: false` unconditionally. Only the *monetized-but-edited*
branch can surface a real signal.

S2 demonstrates this by brigading a published review and showing it never appears in
`get_queue`'s pending list.

### F2 — Velocity detection is upvote-only

`_velocity_flag` filters `ReviewVote.vote == VoteDirection.up` (`fraud_service.py:41`),
so a coordinated downvote raid trips no signal at any volume. S4 demonstrates this.

Recommendation to record (not implement): a symmetric downvote-velocity signal, and
moving signal computation onto published reviews.

## End-to-end layer

One test in `test_ranking_simulation.py`, marked `@requires_db`, proving the feed
actually reorders. Rollback-isolated so it can run against the production Supabase
configuration without persisting anything:

```python
connection = engine.connect()
trans = connection.begin()
db = Session(bind=connection, join_transaction_mode="create_savepoint")
```

`join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0; installed version is 2.0.51)
makes the service layer's internal `db.commit()` release a savepoint rather than commit
the outer transaction.

Sequence:

1. Create two products and two published reviews, plus N voter users, inside the transaction.
2. Assert the initial feed order via `review_service.list_reviews(db, sort="wilson")`.
3. Insert the S2 brigade votes and call the real `recompute_review_vote_aggregates`.
4. Assert the feed order flipped.
5. `finally:` `trans.rollback()`, `connection.close()`.

This exercises the production code path from vote row to feed ordering. It asserts
through the service layer rather than an HTTP call, because the API opens its own
session and would not see uncommitted rows — that is the price of writing nothing, and
it is the right trade.

If `join_transaction_mode` misbehaves against the pooled Supabase connection, the
fallback is an explicit `connection.begin_nested()` savepoint per service call.

## Error handling and determinism

- All generators seeded with `random.Random(42)`; no wall-clock reads in `scenarios.py`
  — ages are passed in explicitly, matching `ranking.py`'s pure-function contract.
- `charts.py` writes into `docs/assets/ranking/`, creating the directory if absent.
- `python -m sim` is idempotent: rerunning overwrites with identical bytes.
- The e2e test skips cleanly via the existing `requires_db` marker when no database is
  reachable, so `python -m sim` and the pure-math assertions still run offline.

## Document

`docs/RANKING_SIMULATION.md`, one section per scenario, each with: setup, graph,
numeric table, "what the website does", finding. Plus a reproduce block
(`cd backend && python -m sim`) and cross-links to ADR-004 and `MILESTONES.md`.

## Out of scope

- Fixing F1 or F2.
- Retuning any ADR-004 constant. The simulation reports behaviour at current values;
  recalibration is an M4→M5 decision per ADR-004's own consequences section.
- Simulating trust-stage progression, payouts, or the earn-eligible gate beyond
  `gate_passes` appearing as a threshold line in S4.
- Load or performance testing — `backend/loadtest/` already covers that.
