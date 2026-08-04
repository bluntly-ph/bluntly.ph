# Algorithm decisions & proposals — 2026-08-03

Answers to every open item from the [2026-07-30 client sync](./2026-07-30-client-sync-updates.md).
Each item is a **decision I'd defend**, not a question. Override any of them — but this is what I'd
build if nobody replies.

Grounded against the code as it stands on `feat/frontend-followups`
(`trust.py`, `ranking.py`, `trust_service.py`, `fraud_service.py`, `honesty_fund_service.py`).

The two decisions with teeth are written up as ADRs in the repo's own format, both citing runnable
simulations under `backend/sim/`:

- [**ADR-014** — helpfulness estimator + evidence gate](./adr/014-helpfulness-estimator-evidence-gate.md)
  — **built and tested** (2026-08-04). This was the live vulnerability.
- [**ADR-015** — Deterrence Delta](./adr/015-deterrence-delta-honesty-fund.md) — **Proposed.**
  Blocked by its own rollout rule, not by effort: it mandates a read-only observation cycle before
  it touches money, and it needs review-view capture that doesn't exist yet.

> **Scope guard applied throughout.** Backend M1–M3 is signed off, paid, and its algorithms are
> documented in `BACKEND_CAPSTONE_PAPER.md` and plotted in `docs/notebooks/bluntly-algorithms.ipynb`
> — the notebook being presented to the panel. Changing any pinned algorithm now would silently
> desync the defense material and move the expected values in 246 passing tests. So: **nothing
> below is implemented yet** — these are specs awaiting a go-ahead. FINDING-1 is the one I'd argue
> for landing soon, and I still didn't touch it.

---

## 🔴 FINDING-1 — Live defect: `helpfulness_ratio` rewards small samples

This is the most important thing in this document, and it wasn't on the meeting agenda. It's the
answer to "how do we calculate the helpfulness score" — and the current answer is exploitable.

**Current implementation** (`trust_service.py:79`):

```python
helpfulness = round(100.0 * helpful / total_votes, 2) if total_votes else 0.0
```

A raw proportion with no confidence correction. **One upvote and zero downvotes scores 100.0/100.**

**Why that matters — the propagation chain:**

`helpfulness_ratio` → 60% of `reputation_score` (`W_HELPFULNESS = 0.60`) → `trust_stage`
(`determine_stage` gates on helpfulness ≥ 70 / 80 / 90) → `gate_vote_weight`
(`STAGE_MULTIPLIER × reputation%`) → honesty-fund payout share (`_review_score`).

**Concrete exploit — run against the real functions, not estimated.** Post 5 reviews, get each
verified, arrange a single upvote on each (one sockpuppet, or a friend):

```
helpfulness_ratio = 100.0
trust_stage       = 3          # clears ">= 5 verified AND helpfulness >= 70"
reputation_score  = 67.78
gate_vote_weight  = 1.0167     # full-strength vote, on 5 votes of evidence
```

Now the same functions for an honest reviewer with **100 votes at 85% helpful**:

```
helpfulness_ratio = 85.0
reputation_score  = 64.22
```

**The 5-vote sockpuppet outranks the 100-vote honest reviewer — 67.78 against 64.22.** That isn't
a subtle bias. The metric actively pays a premium for having almost no data, it inverts the whole
point of the trust ladder, and it sits directly upstream of money.

**The fix is already in the codebase.** `ranking.py` has `time_decayed_wilson()` — used today to
rank *reviews*. Apply the identical function to the *reviewer*:

```python
helpfulness = 100.0 * time_decayed_wilson(
    (v.is_helpful, age_days(v)) for v in votes_on_authors_published_reviews
)
```

What that yields (z = 1.95996, the already-pinned ADR-004 constant — values computed by calling
the repo's own `wilson_lower_bound`, not by hand):

| Evidence | Current | Wilson LB |
|---|---|---|
| 1 helpful, 0 unhelpful | **100.00** | **20.65** |
| 10 helpful, 0 unhelpful | 100.00 | 72.25 |
| 85 helpful, 15 unhelpful | 85.00 | 76.72 |
| 100 helpful, 0 unhelpful | 100.00 | 96.30 |

Small samples are discounted; sustained honest performance wins. Note row 3 against row 1 — the
ordering the current metric gets backwards is restored.

Re-running the exploit above under the fix: helpfulness 100.0 → **56.55**, trust_stage 3 → **2**,
gate_vote_weight 1.0167 → **0.4171**. The sockpuppet loses ~59% of its voting power, while the
honest 100-vote reviewer moves only 64.22 → 59.25.

It also inherits the 45-day half-life for free, so a reviewer's score reflects *recent*
helpfulness rather than a reputation earned once and coasted on — 10 clean votes score 72.25
today and 56.55 once they're a half-life old.

**Why this is cheap to defend at the panel:** no new concept. It's ADR-004 math, already pinned,
already unit-tested, already charted in the notebook (`wilson_lower_bound.png`,
`time_decayed_wilson.png`). The paper's story becomes *stronger*: "we apply the same confidence-
corrected estimator to reviews and to reviewers."

### Correction: Wilson alone is not sufficient

I said earlier that the stage thresholds "must be re-tuned" as if that were routine bookkeeping.
I then tried to derive the re-tuned values, and **the attempt failed in a way that changes the
recommendation.** Reproduce with `python -m sim.helpfulness_estimator`
(`backend/sim/helpfulness_estimator.py`, seeded, ruff-clean).

Thresholds have to drop, because a lower bound is much stricter than a raw proportion — holding
honest reviewers at their historical pass rate (10th percentile, 8 votes/review) gives:

| Stage | Current | Proposed | Gamer scores |
|---|---|---|---|
| 3 | 70 | 49.5 | **56.6** |
| 4 | 80 | 72.9 | **79.6** |
| 5 | 90 | 90.6 | **92.9** |

**The gamer clears the lowered threshold at every stage.** That isn't a bug in the estimator —
5 perfect votes genuinely *are* evidence of quality, and Wilson correctly says so. But it means
lowering thresholds to protect honest progression re-admits the exploit. The score cannot do both
jobs at once.

**So the fix needs a second, independent guard: a minimum-evidence gate.** Require a minimum
*vote* count per stage, not just a review count — no score substitutes for it. At 4 votes/verified
review (20 / 60 / 200 votes for Stages 3/4/5), attacker cost becomes:

| Stage | Arranged votes — shipped | — fixed |
|---|---|---|
| 3 | 5 | **20** |
| 4 | 15 | **60** |
| 5 | 50 | **200** |

**Honest limit:** this raises cost 4×, it does not eliminate the attack. An attacker with enough
distinct qualified voters still climbs. The residual is exactly what the existing velocity and
collusion signals are for — which is the argument for treating this as layered defense rather
than a fix, and for taking B3 (ring detection) seriously alongside it.

Thresholds are also sensitive to the votes-per-review assumption (Stage 3 lands at 38.7 / 49.5 /
57.9 for 4 / 8 / 16 votes per review), so the final numbers should be set from your real vote
data, not from my placeholder. The method is what's settled; the constants aren't.

### Built (2026-08-04)

Shipped as ADR-014 — estimator and evidence gate together, since neither works alone:

- `trust.helpfulness_score()` — Wilson lower bound, replacing the raw proportion.
- `trust.evidence_capped_stage()` — vote-volume gate, composed by `trust_service` around the
  unchanged `determine_stage`. Kept separate so the notebook's pure score ladder still works and
  so no caller can silently omit the gate.
- Thresholds moved to named constants (`STAGE{3,4,5}_HELPFULNESS`).

**One deviation from the proposal:** plain `wilson_lower_bound` on the denormalized vote counters,
not `time_decayed_wilson`. Decay would turn `recompute_user_trust` — which runs on *every vote
write* — from one cheap aggregate into a per-vote scan. Decay addresses staleness; the defect is
small-sample inflation, which plain Wilson fixes. Recorded in ADR-014.

Verified end to end: the 5-vote gamer is capped from Stage 3 → **2** (gate weight 1.0167 → 0.4171);
the honest 100-vote reviewer holds Stage 3. Three integration tests updated off the old literal
`100.0`, three new unit tests added for the discount, the blocked exploit, and the stepwise cap.

**Heads-up for the client:** existing users' displayed helpfulness drops on next recompute
(85.0 → 76.72 for an 85/100 record). No backfill needed — it recomputes on any vote write, publish,
or sweep — but the notebook's numbers will differ from any pre-printed copy, so re-run it before
the defense.

---

## A2 — Comment sentiment as an eligibility input → **No**

The meeting described eligibility as votes *plus* positive comment sentiment. I'd keep votes only.

1. **It re-imports the exact problem you just removed.** AI Critic was pulled from the paper
   because the adviser is strict about AI and would demand model validation. A sentiment classifier
   is the same demand, on the critical path of a payout decision rather than a side feature.
2. **Tagalog/Taglish sentiment analysis is genuinely unreliable** — code-switching, sarcasm, and
   negation flip results, and there's no good pretrained model for it. A wrong classification here
   costs someone money.
3. **Upvotes already are the sentiment signal**, and unlike a classifier they're trust-weighted,
   confidence-corrected, and defensible as arithmetic.

If you want comment activity to count, use a **volume** signal instead of a sentiment one: number
of distinct Stage-2+ users who commented. Countable, unfakeable-by-tone, no model to validate.

---

## A3 — Honesty Fund frequency → **SOLVED. Deterrence Delta (Δd).**

> This supersedes the reach-proxy I proposed earlier today. That was a heuristic. This is a
> measurement, it's unbiased against ground truth in simulation, and it removes the need for the
> seasonal-trend model entirely.

### The move: stop treating deterrence as counterfactual

The meeting stalled on this because a prevented purchase looks unobservable — the sale didn't
happen, so there's no event to log. But you said the thing that unlocks it yourself:

> *"These people will go to the platform for one reason: to buy something. Mag-basa ng review, for
> them to be convinced, and bibili. Punta, basa, bili."*

If that's true — and it is, it's your whole product thesis — then **arriving at a product page is
a declaration of purchase intent.** That's an event. And what happens next is observable in both
directions: they click the affiliate link, or they read a negative review and leave.

We don't have to infer the counterfactual. **We have to instrument the funnel.**

### The control group already exists, and it's contemporaneous

Every product carries both positive and negative reviews, read by the same audience in the same
week. That's a natural control group:

```
r₊  = clicks / views  among sessions that read only POSITIVE reviews of product X
rᵢ  = clicks / views  among sessions that read NEGATIVE review i of product X

Δdᵢ = max(0, (r₊ − rᵢ) − z·SE)          SE = √( r₊(1−r₊)/n₊ + rᵢ(1−rᵢ)/nᵢ )
Dᵢ  = Vᵢ × Δdᵢ                           deterred purchases
valueᵢ = Dᵢ × price × commission_rate     forgone commission, in pesos
```

`z` is `WILSON_Z_95` — the constant already pinned in ADR-004. Nothing new to defend.

### Why this kills the hard part of your seasonal model

Your trend idea was right that demand is the missing variable. But it needed a season or two of
history to establish a baseline, which the capstone doesn't have.

**The difference form makes that unnecessary.** Summer demand for electric fans inflates `r₊` and
`rᵢ` *identically* — same product, same week, same traffic. Christmas gadget spikes, fuel-price
e-bike surges, a viral TikTok: every one of them cancels out of the subtraction. **Δd is
seasonally adjusted by construction.** No trend model, no history, no waiting.

That's the part I'd put in the paper.

### It also replaces the price-bracket multiplier

`honesty_price_multiplier` (1.0 / 1.5 / 2.0×) was a crude stand-in for "expensive products deserve
more" — which really meant "expensive products have bigger forgone commissions." `valueᵢ` computes
that exactly. So this **removes** a pinned magic constant rather than adding one. The model gets
simpler:

```
scoreᵢ = trust_weighted_helpful_votes × valueᵢ
```

### It's ~80% built already

I went looking, and `sessions` (`app/models/session.py`) already records **`review_id`,
`product_id`, `user_id`, `conversion_status`, `clicked_at`** — and `redirect.py` notes the referral
redirect "is the only way out, so clicks are always" attributed. Per-review clicks *and* confirmed
conversions are already captured.

**The only missing piece is `Vᵢ` — a review-view event.** One new table, one endpoint. That's the
entire build.

### Validated in simulation, not asserted

Reproduce with `python -m sim.deterrence_delta` from `backend/`
(`backend/sim/deterrence_delta.py`, seeded, ruff-clean, imports nothing from `app/` but the pinned
`WILSON_Z_95`). Every number below comes out of that module — synthetic world, known ground-truth
deterrence, 400 trials per cell:

**Unbiasedness** — 5,000 sessions per arm, θ = 0.10:

| true deterrence | true deterred | point estimate | conservative |
|---|---|---|---|
| 0.00 | 0.0 | 12.6 | **0.3** |
| 0.10 | 50.0 | **52.5** | 8.9 |
| 0.30 | 150.0 | **152.7** | 98.1 |
| 0.60 | 300.0 | **302.5** | 252.8 |

The point estimator recovers ground truth. The conservative form sits below it — deliberately, so
we underpay rather than overpay. Note the d = 0 row: conservative pays **0.3 instead of 12.6**,
i.e. it declines to invent deterrence that isn't there.

**Small-n safety** — does it pay out on noise?

| sessions/arm | true d = 0 | true d = 0.30 (truth) |
|---|---|---|
| 30 | 0.01 | 0.0 (0.9) |
| 500 | 0.14 | 2.8 (15.0) |
| 2,000 | 0.18 | 27.6 (60.0) |
| 10,000 | 0.48 | 223.9 (300.0) |

It refuses to pay during seeding, then converges as traffic arrives. **Honest tradeoff:** the
conservative form materially underpays at mid-n (27.6 against 60.0 truth at n = 2,000). Since the
pool is proportional, everyone is underpaid by a similar factor and it largely cancels in the
split — but reviewers on thin-traffic products will earn less than they strictly earned. That's
the price of not overpaying, and I'd take it.

### The attack I found, and the fix

The estimator is unbiased but **view-inflation is a serious vulnerability**, because bot views
raise `Vᵢ` *and* depress `rᵢ`, and `D = V × Δd` multiplies both:

| bot views added | estimated D | vs. truth (20.0) |
|---|---|---|
| 0 (honest) | 20.1 | 1.0× |
| 250 | 44.7 | 2.2× |
| 1,000 | 119.5 | 6.0× |
| 4,000 | 418.5 | **20.9×** |

Superlinear. Unmitigated, this is the most attackable surface in the whole payout path.

**Mitigation — count only qualified sessions:** authenticated, account-age ≥ 30 days (the existing
`ACCOUNT_MATURATION_DAYS`), one counted view per user per product per cycle. Bots never enter `Vᵢ`.
Filtered, 4,000 bot views yield **20.1 — exactly the honest value, 1.0× truth.**

And it composes with what's already there: the review must *also* clear the trust-weighted vote
gate to earn, so an attacker needs aged authenticated view accounts **and** trust-weighted upvotes
from established accounts. Two independent defenses, both already specified.

### Where the Yes/No modal now sits

Not in the payout path. You spotted its flaw yourself — someone answers "yes, this helped" with no
intention of ever buying — and being self-reported makes it the easiest input on the platform to
brigade once it pays money.

But it becomes a good **falsification test for Δd**: ship it, log responses, wire it to nothing.
If reviews with high measured Δd also collect more "yes, this helped," the estimator is confirmed
against an independent signal and you can say so at the defense. If they don't correlate, we've
learned Δd is wrong *before* any money moved on it. Zero payout risk either way.

### What this retires

- **The seasonal trend model** — no longer needed for the fund, because the difference form is
  already seasonally adjusted. Still worth building later for *recommendations* — knowing summer
  means fans is genuinely useful for the feed, and `users.interests` (migration `0018`) is the
  seed. It's just no longer load-bearing for anyone's money.
- **The flat-threshold fallback** (₱100/₱200 tiers) — per your instruction, *"let's not build the
  last resort when we still can do something about that number."* We did something about it.
- **`honesty_price_multiplier`** — subsumed by `valueᵢ`, as above.

### Build order

1. Review-view capture, qualified sessions only — the one missing input.
2. Δd computed per review per cycle, **surfaced read-only on the admin card first.** Let it run a
   full cycle where you can see the numbers before a centavo moves on them.
3. Only then wire `valueᵢ` into `honesty_score`, in the same change that drops the price
   multiplier.

Step 2 is the one I'd insist on. It costs one cycle, and it means the first real payout run isn't
also the first time anyone has looked at the estimator's output.

---

## B3 — High-tier collusion → **you're right that it's missing, but half of it exists**

**What exists** (`fraud_service._collusion_flag`): per review, flags when ≥ 5 distinct up-voters
and > 60% of them authored a review the *review's author* also up-voted. That's **pairwise,
author-centric, and computed per queue card.**

**What you described is different** — a *ring*: 50 Stage-6 accounts in a Facebook group, each
upvoting the others. No single pair needs to look suspicious for the group to be rigging outcomes.
The current flag can miss that entirely: spread reciprocity thinly across 50 partners and every
individual pair sits under 0.60.

**Proposed: periodic ring detection.**

```
Nodes  = Stage-4+ users active in the window
Edges  = u → v weighted by |{v's reviews that u up-voted}|
Pair reciprocity r(u,v) = min(w_uv, w_vu) / max(w_uv, w_vu)
Retain edges with r > 0.6 and min(w_uv, w_vu) >= 3
Flag connected components of size >= 3 with mean internal reciprocity > 0.6
```

Runs as a **scheduled Celery job**, not per-request — it's O(n²) over high-tier users, which is
fine nightly and unacceptable inside a queue render. Output: an advisory `collusion_cluster` flag
on the queue card, preserving the existing never-auto-block invariant (FR-8).

Scales fine at your stated numbers: 50 Stage-6 users out of 1,000 → a 50-node graph.

---

## B4 — Helpfulness score → **see FINDING-1 above**, plus a naming fix

Two distinct numbers are both being called "helpfulness score," which is why this felt unresolved:

| Your words | Code | What it is |
|---|---|---|
| "umbrella number for how trustworthy this person is" | `reputation_score` | 0–100 composite: 60% helpfulness + 25% volume + 15% best answers − strikes. **Already exists.** |
| The "Helpfulness Score" field on the admin card | `helpfulness_ratio` | An *input* to the above. Currently the broken raw proportion. |

So the umbrella number you're looking for is already built and already on the card as
`reputation_score`. The field labelled "Helpfulness Score" is one of its ingredients.

**Recommendation:** relabel the admin card — "Trust Score" for `reputation_score` (the umbrella,
the one that tells you what you want at a glance) and "Helpfulness" for the ratio, shown as a
secondary. And fix the ratio per D1.

---

## B5 — Bell-curve voter mix → **right instinct, wrong statistic**

You invited pushback here, so: a normal distribution is the wrong model for this data, and using
it would flag healthy reviews as fraudulent.

Trust stage isn't a bell curve. It's a **heavily right-skewed count distribution by design** — the
ladder is built so most users sit at Stage 1–2 and Stage 5 is rare. A normal distribution assumes
a symmetric bulge around a mean. Fitting one to voter stages would mark the *normal* shape (lots
of low-stage voters, few high) as anomalous — every review would flag.

**What you actually want** — "walang bigla na dito na isang daang libong community expert" — is a
comparison against the *platform's own* mix, which is a goodness-of-fit test:

```
p_s   = platform-wide share of votes cast by stage s (rolling 90d baseline)
e_s   = n × p_s          # expected voters of stage s on this review
χ²    = Σ (o_s − e_s)² / e_s        (df = 5)
Flag if χ² > 11.07  (α = 0.05, df = 5), guarded by n >= 10
```

This catches both directions you named — a flood of Stage-5 voters *and* a wall of newcomers —
because both are departures from the platform's own baseline. And it self-adjusts as the platform
matures, which a fixed curve never would.

Cheap alternative if χ² feels heavy for the paper: per-stage binomial z-score, flag any |z| > 3.
Same idea, one line, easier to explain to a panel.

---

## B6 — One person, one account → **eGov SSO, and the research is done**

Your instinct was right and it's more available than you thought. Findings:

**The portal is real and open:** [platforms.e.gov.ph](https://platforms.e.gov.ph/) — DICT's
Government-as-a-Service API marketplace. Nine APIs including **eGovPH SSO (OAuth 2.0)** and
**National ID eVerify**.

- **Cost: free.** "Free to build on, once your access is approved." Your recollection was correct.
- **Eligibility: "Government agencies, LGUs and accredited private organizations."** Your worry
  about partner-only access was half right — private orgs aren't excluded, but need accreditation.
- **Process:** register org details + declared use case → admin review, *"within a few working
  days"* → sandbox access. Scoped keys are issued after use-case review and a **signed
  data-sharing agreement**.

### Decision: use SSO. Do not use eVerify, and do not use the QR route.

There's a community project, [OpenVerify](https://github.com/bettergovph/openverify), that hits
PhilSys QR endpoints without approval. It returns **full name, date of birth, place of birth,
gender, PCN, and a base64 photo**. Rejecting it on two grounds:

1. **PII blast radius.** That's a near-complete identity dossier per user. You said it yourself:
   *"parang sensitive ng information."* You're right, and we should not hold it.
2. **It runs on undocumented public endpoints and bootstrapped session cookies** — no approval, no
   contract, no stability guarantee, and legally ambiguous. Not something to put under a payments
   platform.

**OAuth SSO gives us exactly what we need and nothing we don't:** a stable subject identifier that
proves one real person. Store a **salted hash of the eGovPH subject ID** (uniqueness enforceable,
original not recoverable) plus **city** (which you asked for). Never store PCN, photo, DOB, or
government-sourced full name.

That's the whole 1:1 guarantee — one eGovPH account, one Bluntly account — at close to zero PII
risk. And it satisfies your "must be very easy" constraint: it's a login button, not a
verification flow we operate.

**Data Privacy Act position under this design:** we hold a pseudonymous identifier and a city.
That's still personal data and still needs a consent notice and a retention policy, but it is not
sensitive personal information, so it avoids the heavier obligations that storing PhilSys numbers
or biometrics would trigger. This is the difference between a manageable compliance footprint and
a serious one.

**Sequencing:** register now — it's free and takes days, and the declared use case is
straightforward. But keep it **off the capstone critical path**, consistent with your own read
that it's "pampabango" and that the Wilson-weighted voting is the real defense. Build the frontend
against a pluggable identity-verification interface so eGov drops in whenever accreditation lands.
I'll need you to do the org registration — it wants organization details.

---

## C1 — Reverse image search → **ADR-007 stands. No external service.**

The meeting leaned toward allowing a plain Google image search. I'd decline, and I think it's what
you actually want given your own constraints:

- You said don't spend resources on it — external image APIs are **metered and paid**, which is
  precisely the cost you rejected for internet-wide plagiarism checking two minutes later in the
  same call.
- Sending user-uploaded photos to a third party creates a PII exposure that ADR-007 was
  deliberately written to avoid — and it's the same photo of someone's purchase.
- **pHash already satisfies the panel requirement.** "Something simple that would satisfy the
  panelist" — a perceptual-hash duplicate-image layer is a real, explainable, demonstrable
  algorithm. It detects the actual fraud case (the same photo reused across reviews, which is what
  a scammer does) better than a global search would, because the fraud is *on-platform*.

Where an external search would genuinely help — "is this photo lifted from the Shopee listing?" —
is exactly the case we can't serve anyway, since we can't crawl Shopee. So we'd be paying for the
capability we can't use.

**No ADR change. Ship pHash, present pHash.**

---

## C2 / C3 / C4 — confirmed as decided in the meeting

- **Plagiarism: Bluntly DB only.** Matches the shipped pg_trgm same-product/same-author
  implementation. No change.
- **AI Critic: left unwired, code stays.** No tokens. On the future licensing note — MIT is a
  permissive free license and works directly against selling it later. If monetization is real,
  that wants a proprietary or dual license. No action now, just don't default into MIT.
- **Q&A tokens: parked, questions stay unlimited.** No change.

---

## D — Admin queue: the "recent activity" item is **not a code bug**

I checked. `QueueItem` (`admin_referral.py:37`) contains: review, product, author, suggested
platform, edited-since-monetized flag, fraud signals, suggested sub-id. **There is no recent-
activity field at all** — not the admin's, not the user's. It exists only in the mockup.

So this isn't "showing the wrong data," it's an unbuilt panel. It becomes a spec item for the
admin dashboard build: a new backend field (the author's last N actions before this post) plus the
frontend to render it. Scoping it as a bug would have sent me chasing code that was never written.

The fraud signals *do* already surface `author_account_age_days` and `author_review_count`, which
covers part of what that panel was for.

---

## Final position

**Honesty Fund: solved, and I'd defend it.** Deterrence Delta measures the prevented purchase
instead of guessing at it, is unbiased against ground truth in simulation, needs one new capture
(review views) because `sessions` already carries clicks and conversions, and retires both the
seasonal-trend model and the price-bracket multiplier. The thing you said you dream about is a
subtraction between two conversion rates you're already most of the way to collecting.

**For the paper, this is the upgrade.** The panel's hardest question — *"how do you know the
review caused the non-purchase?"* — currently has no good answer. Under Δd it has a real one: a
contemporaneous within-product control group, which is a quasi-experimental design, not a
heuristic. That's a stronger methodological story than anything discussed in the call, and it costs
you no extra defending because the estimator reuses ADR-004's pinned `z`.

**Still not built, on purpose.** Backend M1–M3 is signed off and the notebook is defense material.
The only thing I added to the repo is `backend/sim/deterrence_delta.py` — evidence, imported by
nothing in `app/`, ruff-clean. Everything else waits on your word.

**Two things I'd like decided quickly:**

1. **FINDING-1** — the helpfulness-ratio defect. Live hole in a money path, fix reuses code you
   already have, and much cleaner to land *before* the panel sees the current numbers than after.
2. **Δd for the paper** — if you want it in the capstone, say so now. Steps 1–2 of the build order
   (view capture, read-only surfacing) are worth starting even if the payout wiring waits.

**On my side, unblocked and next:** frontend M1–M3 at 1:1 with your Figma. That's the live paid
milestone. Blocked only on the frontend paper, Randy's milestone doc, the contract, and the final
Figma — send those and I start.

---

### Sources

- [eGov API Developer Portal](https://platforms.e.gov.ph/) — API list, eligibility, approval flow, no-fee statement
- [OpenVerify (bettergovph)](https://github.com/bettergovph/openverify) — QR-route implementation and the PII fields it returns
- [eGovPH hackathon coverage, newsbytes.ph](https://newsbytes.ph/2026/07/23/egovph-hackathon-showcases-apis-but-draws-complaints-over-execution/) — the nine opened APIs
