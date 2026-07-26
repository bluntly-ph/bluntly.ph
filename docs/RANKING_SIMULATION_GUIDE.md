# Ranking Simulation — Runbook & Defense Guide

How to run the ranking simulation, how to extend it, and how to demonstrate it live
to a capstone panel.

- **The findings themselves:** [RANKING_SIMULATION.md](RANKING_SIMULATION.md)
- **The parameters:** [ADR-004](adr/004-wilson-decay-velocity-reciprocity.md)
- **Code:** `backend/sim/`, `backend/tests/test_ranking_simulation.py`

---

# Part 1 — Runbook

## One-time setup

```bash
cd backend
python -m venv .venv                      # skip if .venv already exists
.venv/Scripts/activate                    # Windows
# source .venv/bin/activate               # macOS / Linux
pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes `matplotlib`, which the figures need. Runtime
dependencies are untouched — the simulation never ships to production.

## The three commands

| Command | Time | What it proves |
|---|---|---|
| `python -m sim` | ~3 s | Regenerates all four figures, four CSVs, and prints every number the document quotes |
| `python -m pytest tests/test_ranking_simulation.py -q` | ~9 s | All 19, including the three end-to-end tests that prove the feed reorders |
| Same, with DB tests skipped (below) | <1 s | 16 pure-math assertions. **No database needed** |

To skip the database tests, set `SKIP_DB_TESTS` — the syntax differs by shell:

```powershell
# PowerShell (Windows default)
$env:SKIP_DB_TESTS = "1"; python -m pytest tests/test_ranking_simulation.py -q
$env:SKIP_DB_TESTS = $null          # unset afterwards
```

```bash
# bash / zsh / Git Bash
SKIP_DB_TESTS=1 python -m pytest tests/test_ranking_simulation.py -q
```

Expected output either way: `16 passed, 3 skipped`.

Do **not** run the full `python -m pytest` suite during a demo — it is 224 tests and
takes **23 minutes** against Supabase.

## What each file does

| File | Role |
|---|---|
| `sim/scenarios.py` | **Single source of truth.** Vote-stream generators and score series. Pure, seeded, no database, no wall clock |
| `sim/charts.py` | Renders `scenarios.py` output to `docs/assets/ranking/*.png` |
| `sim/__main__.py` | `python -m sim` — writes figures, CSVs, and the headline table |
| `tests/test_ranking_simulation.py` | Asserts on the same `scenarios.py` output the charts use |

That last point is the design's whole safety property: **a committed figure cannot
disagree with a passing test**, because both read the same function. If someone changes
the algorithm, the tests fail — they cannot silently produce a chart that no longer
matches reality.

## Worked example: changing a parameter

Suppose the panel asks "what if the half-life were 20 days instead of 45?"

1. Edit `app/services/ranking.py`:
   ```python
   DECAY_HALF_LIFE_DAYS = 20.0   # was 45.0
   ```
2. Run `python -m sim`.
3. `decay_crossover_day` in the printed table moves — faster decay means the frozen
   champion loses sooner.
4. `python -m pytest tests/test_ranking_simulation.py -q` — expect
   `test_s3_champion_effective_n_follows_the_closed_form` to still pass (it reads the
   constant) but `test_s3_a_frozen_champion_is_overtaken_by_a_steady_challenger` to
   fail if the crossover leaves its documented 30–90 day window.

**Revert before committing** unless the change is intended. ADR-004 requires every
parameter change to move with its test.

## Adding a fifth scenario

Four steps, in this order:

1. **`sim/scenarios.py`** — add a `@dataclass` result type and a generator function.
   Use the existing primitives: `spread_votes`, `burst_votes`, `score_at`,
   `velocity_at`, `rank_among`. Take all randomness from `random.Random(SEED)`.
2. **`sim/charts.py`** — add a `chart_*` function and register it in `render_all()`.
3. **`tests/test_ranking_simulation.py`** — assert every claim the scenario will make.
   If you cannot write the assertion, you do not yet understand the claim.
4. **`RANKING_SIMULATION.md`** — add the section with the figure and table.

Then add the scenario's rows to `summary_rows()` and its numbers to
`headline_facts()` so the CSV and the printed table stay complete.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: matplotlib` | Dev deps not installed | `pip install -r requirements-dev.txt` |
| `ModuleNotFoundError: sim` | Wrong directory | Run from `backend/`, not the repo root |
| 3 tests skipped | No database reachable | Expected offline. The 16 pure-math tests still prove the math |
| Figures look different after a pull | An ADR-004 constant changed | Correct behaviour — the tests should have failed too. Investigate the constant |
| Charts render but text overlaps | matplotlib version difference | `python -m sim` again after `pip install -U matplotlib`; adjust `loc=` in `charts.py` |
| Tests hang for minutes | You ran the whole suite, not this file | Add `tests/test_ranking_simulation.py` to the pytest command |

---

# Part 2 — The live demo

Target: **6 minutes**, leaving the rest for questions. The whole point is that this is
fast — three seconds of compute produces four figures and twenty-odd numbers.

## Pre-flight

**The night before**

- [ ] Run all three commands end to end. Confirm 19 passing.
- [ ] `git status` clean — regenerating figures should produce **no diff** (the sim is
      seeded and idempotent). If it does produce a diff, something is non-deterministic;
      find it before the defense, not during.
- [ ] Open the four PNGs in browser tabs as a fallback.
- [ ] Print or PDF `RANKING_SIMULATION.md`.

**Ten minutes before**

- [ ] Terminal already in `backend/` with the venv activated.
- [ ] Font size up. A panel cannot read 11pt from across a room.
- [ ] Run `python -m sim` once so the interpreter is warm.
- [ ] Confirm the database is reachable — or decide now to run with `SKIP_DB_TESTS=1`
      and say so up front rather than discovering it live.

## The script

**Beat 1 — Frame the question (30 s, no terminal).**

> "Our ranking uses the Wilson score interval. The unit tests prove the arithmetic is
> right. They don't prove the *system* behaves well when a hundred people vote at once.
> So we built a simulation that drives realistic vote floods through the live ranking
> code and measures what happens to the homepage."

**Beat 2 — Run it (30 s).**

```bash
python -m sim
```

Let the headline table land on screen. Say:

> "Three seconds. Four scenarios, four figures, and every number in our report — all
> computed, none hand-written."

**Beat 3 — S1, why Wilson at all (60 s).** Show `wilson_small_n.png`.

> "A naive percentage is flat: one upvote and two hundred upvotes both score 100%.
> Wilson asks the worst plausible true rate at 95% confidence, so it has to be earned.
> Five out of five scores 0.566. Ninety-five out of a hundred scores 0.888 — it ranks
> *higher* despite the lower raw percentage. That's the property that stops the feed
> being owned by whoever got a friend to upvote."

**Beat 4 — S2, the brigade (90 s).** Show `brigade_burst.png`.

> "Two hundred upvotes in ten minutes. The review goes from eighth to first and reaches
> the homepage at minute one. The velocity signal fires at the same minute — two hundred
> an hour against a threshold of ten."

Then pause, and volunteer the bad news before they ask:

> "And nothing happens. The flag is advisory by design. But it's worse than that: we
> traced the code and the flag is never computed for this review at all. That's
> finding F1."

Volunteering the flaw is the single highest-value move in the demo. A panel that finds
it themselves scores you down; a panel you hand it to sees rigour.

**Beat 5 — S3, the silent failure (60 s).** Show `decay_handover.png`.

> "A review with a hundred votes on day zero, never voted on again, versus one earning a
> vote a day. They cross at day 54 — the ordering changes with no new votes at all. But
> that only reaches the site if the nightly recompute job runs. If that job dies, the
> homepage silently freezes and nothing raises an error. That's an operational finding
> we wouldn't have had without simulating time."

**Beat 6 — S4, the asymmetry (45 s).** Show `downvote_raid.png`.

> "A hundred and fifty downvotes in ten minutes. First place to last, below the
> monetization gate, in two minutes. The velocity trace stays flat at False the whole
> time — the detector only counts upvotes. Finding F2."

**Beat 7 — Prove it isn't just a model (45 s).**

```bash
python -m pytest tests/test_ranking_simulation.py -q
```

> "Nineteen tests. Sixteen assert the maths. Three run end to end against the real
> database — real vote rows, the real recompute, the real feed query — and prove the
> ordering actually flips. They run inside a transaction that's always rolled back, so
> they write nothing, which is why they're safe to run against production."

## Fallback ladder

| If this fails | Do this |
|---|---|
| Database unreachable | Skip the DB tests (syntax above) → 16 pass, 3 skip. Say so plainly: "the end-to-end tests need the database; here's the evidence from last night's run" |
| Network entirely down | Everything except the 3 e2e tests works offline. `python -m sim` needs nothing but Python |
| Python environment broken | The four PNGs are committed to git and open in your browser tabs. Walk the figures |
| Laptop dies | The printed `RANKING_SIMULATION.md` has every figure and number |

Note the ladder degrades gracefully by design: the committed figures mean the worst case
is still a complete presentation.

---

# Part 3 — Panel Q&A

Grouped by what they're probing. Each answer names where the evidence lives.

## On method

**"Why the Wilson score interval and not a simple average or percentage?"**
Because a percentage ignores sample size. S1 shows the consequence: 5/5 and 200/200 both
score 100% naively, so a review with one lucky upvote outranks one with two hundred.
Wilson takes the lower bound of a confidence interval on the true positive rate, so more
evidence narrows the interval and raises the score. `wilson_lower_bound` in
`app/services/ranking.py`.

**"Where did z = 1.96, the 45-day half-life, and the threshold of 10 come from?"**
Be honest — this is the question most likely to expose bluffing. z = 1.95996 is the
standard two-sided 95% critical value, which is a real statistical choice. The half-life
and the velocity threshold are **launch calibrations, not empirically derived** — ADR-004
says so explicitly and commits to revisiting them with real vote-volume data at M4→M5.
The simulation is the baseline they'll be recalibrated against.

**"Your vote data is synthetic. How do you know it's realistic?"**
It isn't a traffic forecast and doesn't claim to be. It's a **stress characterisation**:
we impose known inputs and measure the algorithm's response. That's the right instrument
for "how does ranking behave under a brigade" — you cannot answer that with observational
data you don't have yet, and a pre-launch system has none. Every generator parameter is
stated in the document and seeded, so anyone can reproduce or change them.

**"How is this different from your load testing?"**
Load testing (`LOADTEST_RESULTS.md`) measures throughput and latency — can the server
cope. This measures ranking semantics — does the right thing end up on the homepage.
Different failure modes entirely.

## On results

**"So someone can take over your homepage in one minute?"**
Yes, with 200 accounts. Own it — the figure shows exactly that. Then give the cost:
`uq_review_vote_once` means one vote per user per review, so 200 votes needs 200 real
accounts. Registration is rate-limited at 10/minute per IP and voting at 30/minute per
IP. From a single IP that's roughly 20 minutes of account creation. From a botnet it's
trivial. And the limiter **fails open** if Redis is unreachable — a documented property
in `config.py`, not a surprise.

**"Why does the S3 crossover happen while the challenger has *less* effective evidence?"**
A sharp panelist will spot this in the table — 37.38 against 43.53. Both reviews target
95% positive, but `round(n × 0.95)` lands differently on each vote history and the decay
weights fall on different votes, so the challenger's decayed positive fraction is
fractionally higher at that moment. The effective-n curves cross around day 60, slightly
after the score curves. Ordinary sampling texture, and it's stated in the document.

**"Did you actually test this, or just implement it?"**
224 tests pass, 19 of them for this work. Three run end to end against the real database.
The rest of the suite was green on the same commit.

## On weaknesses

**"Why didn't you fix F1 and F2?"**
A scope decision, made deliberately and recorded. Both are pinned by tests asserting
current behaviour, so if anyone fixes them the suite fails and the documentation must be
updated with it — the findings cannot rot. Fixing them properly isn't only code: deciding
what the system *does* when a brigade is detected is a moderation-policy question, and
FR-8 commits us to signals never auto-blocking. That decision belongs with the product
owner, not in a simulation PR.

**"What's the biggest weakness of this work?"**
Have this ready rather than improvising. The honest answer: the scenarios are ones we
thought of. A brigade and a raid are the obvious attacks; a patient adversary voting just
under the threshold for weeks would not show up in any of these four, and we have no
scenario for it. The harness makes adding that scenario cheap — but we haven't.

**"What happens if the nightly recompute job fails?"**
S3 is exactly this. The homepage freezes into whatever was popular the day the votes came
in, and **no error is raised anywhere** — a stored `wilson_score` that is merely stale
looks identical to a correct one. That's the finding, and it argues for alerting on the
job rather than trusting it.

## Do not bluff on these

If asked, the correct answer is some form of "we don't know yet":

- **What real vote volumes will look like.** No production traffic exists.
- **Whether 45 days is the right half-life.** It's a calibration awaiting data.
- **Whether the 0.65 gate is correctly placed.** Same.
- **What fraction of real votes will be fraudulent.** Unmeasured.
- **Whether Wilson is optimal.** It is well-justified and standard; "optimal" is a
  claim we have not tested against alternatives like Bayesian averaging or
  Evan Miller's variants.

Saying "that's outside what we measured, here's what we'd need to answer it" is a strong
answer. Inventing a number is the one thing that can actually sink the defense.

## Claims to make, claims to avoid

| Defensible | Not defensible |
|---|---|
| "Wilson correctly penalises small samples — here is the measurement" | "Our ranking is fraud-proof" |
| "A 200-vote brigade reaches the homepage in one minute" | "We prevent brigading" |
| "The velocity signal never fires on a downvote raid" | "We detect coordinated attacks" |
| "The nightly job is load-bearing and unalarmed" | "The system is self-healing" |
| "These parameters are launch calibrations to be revisited" | "These parameters are optimal" |
| "19 tests pin every claim in this document" | "The ranking is fully tested" |

The pattern: claim what you measured, in the words you measured it in. Every row on the
left is backed by a named test; nothing on the right is backed by anything.
