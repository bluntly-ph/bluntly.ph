# ADR-015: Deterrence Delta (Δd) — the Honesty Fund frequency term

- **Status:** **Proposed** (2026-08-04) — deliberately not built yet.
  Would replace `honesty_price_multiplier` (FR-6) in `honesty_score`.
- **Why not now:** the platform is pre-launch with no traffic, so the view-capture
  table this needs would collect nothing, and the read-only observation cycle the
  rollout requires has nothing to observe. Shipping an unused table and public
  endpoint days before a defense adds attack surface and yields no data. Build it
  at launch, when the first real sessions make it worth having. Roughly an hour of
  work — the blocker is timing, not effort.
- **Context:** The Honesty Fund pays a reviewer the affiliate commission they *would*
  have earned had their negative review not prevented purchases. Price and commission
  rate are known; the number of prevented purchases is not. It reads as a
  counterfactual — no sale, no event — and has been the open question in FR-6 since M2.
  The interim stand-in, `honesty_price_multiplier` (1.0/1.5/2.0× by price bracket), is
  a proxy for "expensive products forgo more commission" rather than a measurement.

  A session arriving on a product page has already declared purchase intent (PRD §2).
  Sessions that read only *positive* reviews of that product are therefore a
  contemporaneous control group for sessions that read negative review *i*.

## Decision
Estimate deterrence as the conversion gap between the two arms:

| Term | Definition |
|---|---|
| `r₊` | clicks / views, sessions reading only positive reviews of the product |
| `rᵢ` | clicks / views, sessions reading negative review *i* |
| `Δdᵢ` | `max(0, (r₊ − rᵢ) − z·SE)`, `SE = √(r₊(1−r₊)/n₊ + rᵢ(1−rᵢ)/nᵢ)` |
| `Dᵢ` | `Vᵢ · Δdᵢ` — deterred purchases |
| `valueᵢ` | `Dᵢ × price × commission_rate` — forgone commission, in pesos |
| `scoreᵢ` | `trust_weighted_helpful_votes × valueᵢ` (replaces the price multiplier) |

`z` is `ranking.WILSON_Z_95`, already pinned by ADR-004. `Vᵢ` counts **qualified
sessions only**: authenticated, account age ≥ `ACCOUNT_MATURATION_DAYS`, one per user
per product per cycle.

## Consequences
- **Seasonality cancels.** Both arms are drawn from the same product in the same
  window, so demand swings (summer cooling, Christmas gadgets, fuel-price e-bikes)
  affect `r₊` and `rᵢ` equally and drop out of the subtraction. No trend model, and no
  history required before the fund can run — which is why the seasonal-demand design
  is not needed for payouts.
- **Removes a pinned constant** rather than adding one: `honesty_price_multiplier`
  is subsumed by `valueᵢ`.
- **Conservative by construction, and it underpays.** Subtracting the CI margin means
  thin-traffic reviews earn less than they strictly earned (27.6 against 60.0 truth at
  n = 2,000/arm). The pool is proportional, so this largely cancels in the split.
- **View inflation is the main attack surface** and is superlinear — bot views raise
  `Vᵢ` and depress `rᵢ`, and `D = V·Δd` multiplies both: 4,000 bot views yield **20.9×**
  the true value. The qualified-session rule above returns it to 1.0×; it is not
  optional.
- **Requires one new capture:** a review-view event. `sessions` already records
  `review_id`, `user_id`, `conversion_status`, `clicked_at`, and `redirect.py` is the
  only egress, so clicks and conversions are already attributed per review.
- **Rollout:** surface Δd read-only on the moderator card for one full cycle before
  wiring it to `honesty_score`.
- Evidence: `backend/sim/deterrence_delta.py` (`python -m sim.deterrence_delta`) —
  unbiased against known ground truth (152.7 vs 150.0; 302.5 vs 300.0), declines to
  pay on noise (0.3 vs a 12.6 point estimate at true deterrence 0).
