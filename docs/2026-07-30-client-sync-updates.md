# Client sync — 2026-07-30: updates to set

Source: meeting recording `Screen Recording 2026-07-30 002513` (1:16:00, full transcript).
Participants: client/product owner + Bash (backend + frontend, cyber-sec).

Status legend — **DECIDED** = client stated it plainly, just needs implementing ·
**OPEN** = client explicitly asked Bash to propose/research · **PARKED** = deliberately
deferred, do not build now · **FYI** = context, no action.

Everything below is my reading of the call. Correct anything I got wrong before I touch code.

---

## A. Honesty Fund — the one unsolved problem

The client called this the platform's main selling point and the thing he thinks about daily.
Nothing here is final; he asked for proposals.

### A1. The reward baseline — **DECIDED** (already matches the build)
Every product carries an affiliate commission percentage (5% / 10% / 20%). A negative review
*prevents* a purchase, so the reviewer never earns that commission. The Honesty Fund pays that
forgone commission instead.

> ₱100 product × 5% commission = ₱5. That ₱5 is the reviewer's *supposed* reward → it becomes
> the baseline the fund works from.

Current code already does the pool side of this: `honesty_fund_service.distribute()` splits the
30% fund share of a cycle's commissions across eligible (≤2-star, published) reviews, weighted by
`honesty_score` = trust-weighted helpful votes × price bracket. **No change needed to the pool
mechanism.** What is missing is A3.

### A2. Eligibility is community-gated — **DECIDED** (already matches the build)
A reviewer is only eligible if the community actually found the review useful — enough weighted
votes, plus positive sentiment in the comments ("thank you for this review"). A review that just
trashes a seller with no substance earns nothing.

> "Kunyari siniraan ko lang yung seller... walang kwenta. Di pwede may earnings ako doon."

Gate already exists (`gate_vote_weight` + earn-eligible routing). **Open sub-item:** comment
*sentiment* is not currently part of the gate — only votes are. Confirm whether sentiment should
become a real input or stay as the informal description of what upvotes already proxy.

### A3. The missing multiplier: **frequency** — **OPEN, highest priority**
We know the price and the commission %. We do **not** know *how many people were deterred* from
buying by the negative review. A positive review's conversion is observable (100 people bought);
a negative review's non-conversion is invisible.

> "Yung 5 pesos na yun is one time lang. What if mayroong isang daang tao yung dapat bibili nun,
> pero hindi na lang? Where will we get the multiplier?"

Three inputs to the final number, per the client: **(1)** comment sentiment / helpfulness,
**(2)** commission % — concrete and measurable, **(3)** frequency — the hard one.

Two candidate approaches were discussed:

**Approach 1 — "Did this help?" modal (Bash's proposal).** After reading a review, a one-click
Yes/No pop-up: *"Did this review help you with your purchase decision?"* Log the yeses as the
frequency signal.
- Client: "that's the simplest approach, but that might also be the best one we have right now" —
  accepted as a **starting point**, not the answer.
- Client's own objection: someone can answer Yes with no intention of ever buying → weak proxy.
- Gaming risk to solve before shipping: needs Wilson-score / weighted-vote treatment so a
  level-1 Yes is not worth a level-6 Yes.

**Approach 2 — demand-trend derived frequency (client's proposal, preferred long-term).**
Derive frequency from what people *search for* on Bluntly, not from what they claim.
- Basis: his 13k-member subreddit analytics show hard seasonal trends — summer → electric fans /
  aircon, Christmas → gadgets, fuel price spikes → e-bikes, rainy season → power banks,
  flashlights, raincoats.
- Mechanism: capture intent on entry (small pop-up: *"What are you looking for today?"*) plus
  logged search queries → build a per-product/per-category demand trend.
- Then discount it: of 100 people searching a product review, only some fraction would truly have
  bought. That conversion percentage "is supposed to come from somewhere na na-measure talaga,
  hindi hula-hula lang."
- Final shape: `reward = commission_amount × frequency_multiplier`, then gated by the weighted
  voting approval, paid out of the fund pool.
- Client's own caveat: "not easy for the start, I admit. So we need to find a phase 1 phase 2 din
  dito." → **deliverable: a phased plan, Approach 1 as Phase 1, Approach 2 as Phase 2.**

### A4. Last-resort fallback — **PARKED, explicitly do not build**
If no measurable frequency is ever found: drop the variable number and use flat threshold payouts
(hit threshold → ₱100 / ₱200, sized to the fund balance).
> "Let's not build the last resort when we still can do something about that number."

---

## B. Anti-gaming / trust — what the client considers the actual product

### B1. The backbone is proprietary — **FYI**
Weighted voting system + trust levels (1–6) + Wilson score interval. Everything else
(reverse image, plagiarism, AI critic) is explicitly a side layer.

### B2. Low-tier vote inflation — **DECIDED, already built, no change**
Level-1 weight is 0.25 → 4 sockpuppets = 1 real vote. Client walked through this himself and is
satisfied: a 1,000-account farm is more effort than just writing honest reviews.

### B3. High-tier collusion detection — **OPEN, new work**
The gap he wants closed: level-6 accounts are few and powerful, and can form rings — a Facebook
group agreeing to upvote each other, producing near-1:1 reciprocal vote ratios.

> "Itong user na to na level 6 at itong user na to na level 6 ay most often na ina-upvote yung
> post ng isa't isa, and there's a pattern to it."

Reality check against the code: a reciprocity flag **already exists** —
`fraud_service._collusion_flag` flags a review when ≥5 distinct up-voters and >60% of them
authored a review the author also up-voted (advisory only, surfaced on the moderator card, never
auto-blocks). The client believes this is not in the codebase yet, so either he hasn't seen it or
he means something broader.

**What is genuinely new in his ask:** cluster/ring detection *across* users (a group of N
high-tier accounts with mutually elevated vote overlap), not just the pairwise author↔voter
reciprocity we compute per review. Needs confirmation on which he means.

He also asked Bash directly to propose additional security measures here, on the grounds that
real money is involved and Bash is the security person.

### B4. Helpfulness score — **OPEN, client does not know how to compute it**
Shown on the admin card. Meant to be the reviewer's umbrella trust number:
> "parang an umbrella number para sa kung gaano katiwala-tiwala tong taong ito. Pag nababa yan,
> edi alam mo na."

His own guess is upvotes-vs-downvotes consolidation; he asked for something better and asked to
"talk about that later." **Also needs reconciling with the existing `reputation_score` in
`trust.py`** — we should not ship two competing trustworthiness numbers.

### B5. Voter-mix sanity via normal distribution — **OPEN**
He wants the voter composition on a review judged against a bell curve: a healthy review's voters
should look like a normal distribution across tiers. Anomalies (100k community experts appearing
at once, or 100 newcomer upvotes and nothing else) should be flagged.
> "Maybe it should be based around the bell curve... walang bigla na dito na isang daang libong
> community expert or vice versa. Or, if there's another graph that's better, feel free to propose."

### B6. One person = one account — **OPEN, research task**
Problem: mobile-number verification is weak (people have many numbers), and IP whitelisting is
pointless because residential Philippine IPs are dynamic. He wants a per-person risk score for
multi-account holders, ideally a literal 1:1 guarantee.

**Bash's proposal, which the client is enthusiastic about: the eGov PH API as SSO.**
- Believed free (a colleague used it); ties to the national ID (PhilSys), not publicly searchable
  but API-verifiable.
- Client: "I'm very interested in your proposal. Please look more into it. Gusto ko siya."
- Hard constraint from the client: **it must be very easy** — he does not want a heavy
  verification process of our own on top of it.
- He also wants to **capture the user's city** from it.
- He wants the returned data stored in our own database.
- Possible blocker raised in the call: the API may only be available to partnered/affiliated
  institutions — needs checking. He may have a government contact who could help.

> ⚠️ **My flag, needs the client's decision:** storing national-ID-derived identity data puts us
> squarely under the Philippine Data Privacy Act — that means a lawful-basis/consent flow, a
> retention policy, encryption at rest, and breach-notification duty. He raised the sensitivity
> himself ("parang sensitive ng information, are we gonna store that sa database natin?") and
> answered yes. Before I build this I want an explicit go-ahead that we're taking on that
> obligation, and ideally we store a verification *result* + city rather than the raw ID payload.

- Non-blocking either way: he considers this "pampabango" / added security. "If ever na hindi,
  that's fine. Like isang user na may sampung account, that's fine, kasi it wouldn't change
  anything because of the Wilson score interval." The voting system is the real defense.

---

## C. Side features — scope explicitly reduced

### C1. Reverse image search — **DECIDED: minimal, low effort**
- We cannot scrape or crawl Shopee (prohibited) and have no database access.
- Acceptable scope: a plain general search-engine image lookup to see whether an uploaded photo
  already exists identically elsewhere. "Sadyang sa Google search lang talaga."
- Pulling images/reviews directly off Shopee was discussed and set aside as a gray area —
  "siguro in the future na yun."
- Paid search APIs: "if that's the case, it's a minor feature lang naman. We don't have to spend
  too much resources on it." Something simple that satisfies the panel is enough.

> ⚠️ **Conflict to resolve:** ADR-007 currently specifies **on-platform pHash only** and
> explicitly rules out external services (Google Vision, TinEye) to avoid third-party PII
> exposure. This meeting softens toward permitting an external general image search. Either
> ADR-007 gets superseded or we keep pHash and present that as the layer. **Needs a decision.**

### C2. Plagiarism check — **DECIDED: Bluntly database only**
Internet-wide checking is paid and impractical; client agreed immediately. Future nice-to-have:
scope it to specific sites (Reddit, Shopee, Lazada). Current pg_trgm same-product/same-author
implementation matches what he expects.

### C3. AI Critic — **PARKED, keep the code, leave it unwired**
- **Removed from the capstone paper.** The adviser is strict about AI and would demand model
  validation; not worth the effort for a sub-feature. "We're gonna use that, just not for the
  capstone."
- Stays in the codebase for future implementation. No tokens wired.
- Long-term vision: train it on what admins actually approve/reject, building our own dataset
  because no such dataset exists. Possibly a sellable asset later, which would need T&C and a
  license.

> Minor flag: MIT was named as the candidate license. MIT is permissive/free and works against
> selling it. If monetization is the goal, that should be a proprietary or dual license. "Future
> na yan, masyado pa tayong maaga" — so no action now, just don't lock MIT in by default.

### C4. Q&A tokens — **PARKED, keep questions unlimited**
Questions are currently free and unlimited. Answers carry affiliate links, so questions are a
revenue avenue — he does not want to suppress them. But he also doesn't want people asking
endlessly instead of reviewing. Both sides were argued and he closed it:
> "For now, let's put that sa parking lot muna and go with the idea na wala. Tanong ka as much as
> you want."

---

## D. Admin review queue (the screen he walked through)

What was shown is a **sample, not the final design** — the final comes from his Figma.
Card contents he confirmed: title, star rating, common tags, eligibility + priority (a level-6
author is high priority), photo count, business/velocity score, a required-details checklist with
an ✗ for anything missing, account age, verified reviews (= admin-approved), total reviews,
helpfulness score (see B4), plagiarism score, product context, recent activity, and the voter
summary (the collusion view — e.g. 17 contributors, author is level 2, voters are fellow
contributors plus one community expert → probably legit).

Purpose: the admin should be able to decide from the overview alone without reading the whole post.

### D1. **BUG — recent activity shows the wrong user**
> "Ito yung recent activity niya. Ay, no, sorry — recent activity nung admin. But this is supposed
> to be the recent activity nung user."

The panel must show the **reviewer's** activity leading up to the post, not the admin's.

### D2. One field label is too long — he will revise it himself. No action.

### D3. Plagiarism score on the card reads against our own DB only for now (per C2).

---

## E. Frontend — the actual next milestone

### E1. Backend M1–M3 are accepted and closed — **FYI**
> "Tapos na yung M1, M2, M3. Wala na akong i-inspect doon. Maybe kung may changes man in the
> future, I'll just relay it to you."
The Google Colab notebook was specifically appreciated — he'll present it directly to the panel.

### E2. **Hard requirement: 1:1 fidelity with the Figma design**
This is the one thing he pressed on repeatedly. Claude Code is fine, hand-coding is fine, "no
judgment" — but whatever he designed in Figma is exactly what must appear on the live site.
> "As long as yung design is how I design it sa Figma."

He has been disappointed by AI-generated design ("it feels so AI") and has no UI/UX specialist,
so fidelity to *his* design is how he's controlling for that.

### E3. The frontend must run against the working backend
So upvotes and the rest are testable end-to-end during QA.

### E4. QA is the client + Nate. Nate offered to help on backend; declined, backend is done.

### E5. Frontend milestones mirror the backend: M1 / M2 / M3, where **M3 = all pages working,
functioning, and built.** He is sending the frontend paper, Randy's milestone doc, and the
contract to sign. He also asked Bash to check the shared docs and set another milestone there if
needed.

### E6. Frontend security is expected to be handled — he's not worried, on the basis that Bash is
the security person, and noted AI-generated frontends typically ignore it.

---

## F. Minor / no action

- **CSV export:** manual download is fine for now. OTP-by-email is fine. Sorting is fine.
  "Kung may problema doon, madali yung problem na ma-fix." Not worth meeting time.
- **Payment:** delayed — his bank account is under inspection (student work classification, unusual
  in/out flows), 3–5 business banking days, expected Tuesday or Wednesday next week. He'll sign
  that night.
- **BIR/TIN:** secured. Applied July 5, received ~July 28.
- **Design help:** he suggested screenshotting into Claude design for the admin dashboard; he's
  tried it before and was unimpressed, will try again.

---

## Action list — mine, in priority order

| # | Action | Type |
|---|--------|------|
| 1 | Phase 1 / Phase 2 plan for Honesty Fund frequency (A3): "Did this help?" modal now, demand-trend later | proposal |
| 2 | Anti-gaming design for the Yes/No modal (weighted by tier, Wilson-treated) | proposal |
| 3 | Clarify B3 — is the existing reciprocity flag what he wants, or true multi-account ring/cluster detection? | question |
| 4 | Propose the helpfulness-score formula + reconcile with existing `reputation_score` (B4) | proposal |
| 5 | Propose the bell-curve voter-mix anomaly check (B5) | proposal |
| 6 | Research eGov PH API — availability, partner requirement, effort, what it returns, city capture (B6) | research |
| 7 | Get an explicit decision on storing national-ID PII + Data Privacy Act obligations (B6 flag) | question |
| 8 | Resolve the ADR-007 conflict: external image search vs. on-platform pHash (C1) | question |
| 9 | Fix admin card "recent activity" to show the reviewer, not the admin (D1) | bug |
| 10 | Frontend M1–M3 against Figma at 1:1, wired to the live backend (E2, E3, E5) | build |
| 11 | Additional security proposals for the money-handling paths, as he asked (B3) | proposal |

## Waiting on the client

- Frontend paper + Randy's milestone doc + contract to sign (E5)
- The docs link he mentioned sending (E5)
- Final Figma for the admin dashboard (D)
- Answers to questions #3, #7, #8 above

---

## Open items — now answered

Every question this document raised has been decided in
**[2026-08-03-algorithm-decisions.md](./2026-08-03-algorithm-decisions.md)**. Summary:

| Item | Decision |
|---|---|
| A2 — sentiment as eligibility input | **No.** Re-imports the AI-validation problem you just removed from the paper; votes already carry the signal |
| A3 — frequency multiplier | **Solved — Deterrence Delta (Δd).** Measure the prevented purchase as the conversion gap between readers of positive vs. negative reviews on the same product. Unbiased in simulation; retires the seasonal-trend model *and* the price multiplier; Yes/No modal demoted to a falsification test |
| B3 — collusion | **Both.** Pairwise exists; ring/cluster detection is genuinely missing — spec'd as a nightly graph job |
| B4 — helpfulness score | **Already exists as `reputation_score`** — and its input `helpfulness_ratio` has a live defect (see below) |
| B5 — bell curve | **Rejected the statistic, kept the goal.** Stage mix is right-skewed by design; χ² against the platform baseline instead |
| B6 — eGov | **SSO (OAuth2), not eVerify, not QR.** Free, ~few days to approve; store hashed subject ID + city only |
| C1 — ADR-007 | **Stands.** Keep on-platform pHash, no external image service |
| D1 — recent activity | **Not a code bug** — the field never existed; it's an unbuilt panel |

**⚠️ Escalation not raised in this meeting — FINDING-1:** `helpfulness_ratio` is a raw proportion,
so a 5-vote sockpuppet account currently scores **67.78** reputation against **64.22** for an
honest reviewer with 100 votes at 85% helpful. Live hole in a money path; the fix reuses code
already in `ranking.py`. Verified numbers and the propagation chain are in the decisions doc.
