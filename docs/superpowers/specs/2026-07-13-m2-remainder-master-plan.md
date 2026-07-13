# M2 Remainder — Master Implementation Plan (slices 2–8, complete)

**Date:** 2026-07-13 · **Planned on:** Fable 5 (final planning pass — no further
Fable sessions needed for M2) · **Implemented on:** Opus 4.8, **one slice per
session**, in order. Every parameter, schema, endpoint, and edge case is pinned
here; if an implementer hits something genuinely undecidable, stop and ask the
product owner — do not improvise a design.

**M2 scope remaining** (from `docs/MILESTONES.md`; slice 1 referral flow is DONE):
Wilson trust ratings (product + seller) · fake/shill detection · collusion
detection · trust threshold configuration · upvote/downvote with anti-manipulation
· tier-based revenue split · token economy data models with transaction history —
plus the M0 Celery stubs that M2 owns (commission CSV reconciliation, Honesty Fund,
PII retention).

**As-built inventory the slices build on (verified):** pure tested functions in
`app/services/ranking.py` (wilson_lower_bound, time_decayed_wilson, decay_factor,
velocity_exceeded, reciprocity_flag), `trust.py` (reputation_score,
determine_stage, gate_vote_weight, honesty_score), `earnings.py`
(split_commission); tables `seller_reviews`, `commissions`,
`honesty_fund_distributions`, `sessions`, `moderation_logs` exist but are unwired;
`reviews.helpful_votes/unhelpful_votes/wilson_score` columns exist; **no vote
table, no vote/seller-review endpoints, Celery task bodies are stubs.**

---

## Standard per-slice checklist (applies to EVERY slice; do not restate per slice)

1. Read this spec section + the files you'll touch. Migration via Alembic
   (autogenerate then hand-check; enum ADD VALUE → `autocommit_block()`), fully
   reversible, RLS enabled on any new table (public SELECT policy, consistent with
   existing style).
2. New settings go in `app/core/config.py` (+ `.env.example` with comments).
3. Unit + integration tests (pattern: `tests/test_*_api.py` with
   `register_and_token`); extend `scripts/api_smoke.py` with the new endpoints.
4. `ruff` clean · full `pytest` green · migration applied to **local AND Supabase**
   (session pooler) · `docker compose up -d --build` healthy · run
   `python -m scripts.api_smoke --base-url http://localhost:8000 --concurrency`.
5. Docs: `docs/schema.md`, `docs/DEVIATIONS.md`, `backend/API_TESTING.md`,
   `docs/ARCHITECTURE_AS_BUILT.md` (§6/§12), re-export `docs/openapi.json`.
6. Never auto-block on fraud signals — **advisory to the moderator only** (capstone
   FR-8 invariant). No scraping, ever.

---

## Slice 2 — Community voting + time-decayed Wilson visibility ranking

**Goal:** equal-weight up/down votes on published reviews; Wilson-ranked listings;
anti-manipulation guards; author helpfulness feeds reputation.

### Schema (migration `0005_review_votes`)
- Table `review_votes`: `id` UUID PK · `review_id` FK reviews CASCADE ·
  `voter_id` FK users CASCADE · `vote` (existing `vote_direction` enum up/down) ·
  timestamps · `UNIQUE (review_id, voter_id)` (one vote per user per review;
  changing = upsert) · index on `review_id`. RLS: public SELECT.

### Endpoints
| Method & path | Auth | Behavior |
|---|---|---|
| `POST /api/v1/reviews/{id}/vote` `{vote: up\|down}` | user | Upsert own vote. Guards: review must be **published** & not removed (404 otherwise); **no self-vote** (409 `cannot_vote_own_review`); rate-limited (bucket `vote`, `VOTE_RATE_LIMIT_MAX=30`/60s reusing the existing limiter). Returns updated ReviewOut. |
| `DELETE /api/v1/reviews/{id}/vote` | user | Remove own vote (404 `vote_not_found` if none). |
| `GET /api/v1/reviews?sort=wilson\|newest` | public | `newest` stays default; `wilson` orders by `wilson_score DESC, created_at DESC`. |

### Logic (service `app/services/vote_service.py`)
- On every vote write/delete, in ONE transaction: update the vote row; recompute
  `reviews.helpful_votes/unhelpful_votes` (COUNT by direction) and
  `reviews.wilson_score = time_decayed_wilson([(v.vote==up, age_days(v.created_at))...])`
  (existing function, half-life 45d per ADR-004); recompute the **author's**
  `helpfulness_ratio` = 100 × Σhelpful / Σ(helpful+unhelpful) across their published
  reviews (0 if no votes); then call `recompute_user_trust` (slice 3 — if slice 3
  isn't merged yet, leave a `# slice-3 hook` comment instead).
- **Velocity flag** is NOT stored: computed on read in the moderator queue (slice 5).
- Nightly Celery task `recompute_wilson_scores` (beat: 04:00 Asia/Manila): recompute
  decayed wilson for all published reviews with ≥1 vote (decay drifts with time).
  Real body now, not a stub.

### Tests (minimum)
Self-vote 409 · anon vote 401 · vote on unpublished 404 · upsert changes direction
(counters right) · delete vote · wilson_score >0 after up-votes and ordering works
via `?sort=wilson` · author helpfulness_ratio updates · unique constraint holds.

---

## Slice 3 — Trust progression wiring (reputation, stages, badges)

**Goal:** users' `reputation_score` / `trust_stage` actually move; stage badges awarded.

### No schema change (columns exist). Badge codes exist in seed.
### Logic (service `app/services/trust_service.py`)
- `recompute_user_trust(db, user_id)`: recompute inputs → `verified_review_count`
  = COUNT of the user's **published**, verified, not-removed reviews;
  `helpfulness_ratio` (as slice 2); `best_answer_count` stays as-is (Q&A unbuilt);
  `months_active` = (now − user.created_at).days / 30. Then
  `reputation_score(...)` and `determine_stage(review_count=COUNT published
  reviews, ...)` (existing pure functions). Persist both.
- **Stages only via this recompute** — no manual stage set endpoint (moderator
  penalties come later with strikes; out of M2).
- **Badge award:** when `trust_stage` increases into 2..5, insert `user_badges` row
  for the matching seeded badge (`verified_buyer`, `established_reviewer`,
  `trusted_reviewer`, `community_expert`) if absent. No badge removal on stage drop.
- **Triggers:** call from — review publish/unpublish/reject (referral_service),
  vote writes (slice 2), and a nightly Celery sweep `recompute_all_trust` (04:30)
  over users active in the last 90 days (updated_at or with recent votes/reviews).
- Endpoint: `GET /api/v1/users/{id}/trust` (public): `{trust_stage,
  trust_level_name, reputation_score, verified_review_count, helpfulness_ratio,
  badges:[{badge_id,name,awarded_at}]}`.

### Tests
Publishing a verified review moves a fresh user to stage 2 + badge awarded once ·
helpfulness changes move reputation_score deterministically (assert exact values
from the ADR-003 formula) · stage never set by API directly · endpoint shape.

---

## Slice 4 — Seller reviews + product/seller trust ratings + visibility thresholds

**Goal:** wire the existing `seller_reviews` table; compute Wilson trust ratings
for products and sellers; config-driven visibility thresholds.

### Schema (migration `0006_trust_ratings`)
- `products.trust_score` Numeric(6,5) NOT NULL default 0.
- `users.seller_trust_score` Numeric(6,5) NULL (only meaningful for sellers).
- No new tables (`seller_reviews` exists with accuracy/order_completeness/
  customer_service/packaging_quality/overall_rating/would_recommend/proof_url).

### Endpoints
| Method & path | Auth | Behavior |
|---|---|---|
| `PATCH /api/v1/users/{id}/role` `{role: seller\|user}` | moderator | Promote/demote seller (moderator cannot grant `moderator` via API — 422). Audit-log (`moderation_logs`, action `override`, note "role change"). |
| `POST /api/v1/sellers/{seller_id}/reviews` | user | Body: `accuracy: bool, order_completeness: bool, customer_service: 1..5, packaging_quality: 1..5, overall_rating: 1..5, would_recommend: bool, product_id?: UUID, proof_url?: str`. Guards: target must have role=seller (404 `seller_not_found`); no self-review (409); **one seller review per (seller, reviewer)** — enforce with a unique partial check in service + DB unique index `uq_seller_review_once (seller_id, reviewer_id)` in the migration. Publishes immediately (seller reviews are NOT publication-gated — no monetization attached; document as deviation). |
| `GET /api/v1/sellers/{seller_id}/reviews` | public | List, newest first, `limit≤100`. |
| `GET /api/v1/sellers/{seller_id}` | public | Profile: display_name, seller_trust_score, per-dimension averages + counts (computed live), would_recommend %, review_count. |

### Trust rating math (pinned)
- **Seller trust** = `time_decayed_wilson([(sr.would_recommend, age_days)...])`
  over their seller_reviews. Recompute on each seller-review write + nightly.
- **Product trust** = `time_decayed_wilson([(r.star_rating >= 4, age_days)...])`
  over the product's **published**, not-removed reviews. Recompute on publish/
  unpublish/edit-of-stars + nightly (same 04:00 task as slice 2 extends).
- Store per-dimension seller aggregates in `users.seller_aggregates` JSONB
  (`{accuracy_pct, completeness_pct, customer_service_avg, packaging_avg,
  recommend_pct, count}`) on each write.

### Visibility thresholds (config; defaults OFF for cold start)
- `PRODUCT_TRUST_VISIBILITY_THRESHOLD: float = 0.0`,
  `PRODUCT_TRUST_MIN_REVIEWS: int = 5`, `SELLER_TRUST_VISIBILITY_THRESHOLD: float = 0.0`.
- Rule: a product is **excluded from default `GET /products` listing** iff
  `review_count >= PRODUCT_TRUST_MIN_REVIEWS AND trust_score <
  PRODUCT_TRUST_VISIBILITY_THRESHOLD`. Always retrievable by ID with a computed
  `low_trust: true` field; `?include_low_trust=true` shows all. Same pattern for
  sellers on their profile (`low_trust` flag only — never hide the profile).
  Thresholds are env config; changing them needs no code (document in PRODUCTION.md).

### Tests
Role promotion RBAC · self-review 409 · duplicate seller review 409/constraint ·
dimension aggregates math · seller trust moves with would_recommend votes ·
product trust_score computed from stars · threshold exclusion kicks in only at
min_reviews (set thresholds via settings override in test) · `low_trust` flag.

---

## Slice 5 — Fraud signals: fake/shill + collusion detection (advisory)

**Goal:** surface signals on the moderator queue card. **Never auto-block.**

### Schema (migration `0007_pg_trgm`)
- `CREATE EXTENSION IF NOT EXISTS pg_trgm;` (available on Supabase; wrap in
  try/exception-comment — if the local image lacked it, postgres:16 has it).
- GIN index `ix_reviews_discussion_trgm ON reviews USING gin (discussion gin_trgm_ops)`.

### Signals (computed on read in `referral_service.get_queue` → new
`app/services/fraud_service.py`; added to `QueueItem.signals`)
```json
"signals": {
  "velocity": bool,            // velocity_exceeded over the review's votes (existing fn, >10 up-votes/hour)
  "collusion": bool,           // see definition below
  "duplicate_content": bool,   // max pg_trgm similarity vs OTHER reviews (same product OR same author) > 0.85
  "duplicate_of": "review_id|null",
  "author_account_age_days": int,
  "author_review_count": int
}
```
- **Collusion (pinned, implementable):** let A = review author, V = distinct
  up-voters of this review. `mutual = |{V : A has up-voted ≥1 of V's reviews}|`.
  Flag iff `len(V) >= 5 AND mutual/len(V) > 0.6` (constants
  `COLLUSION_MIN_VOTERS=5`, `COLLUSION_THRESHOLD=0.6` in `ranking.py` — reuse the
  ADR-004 numbers).
- **Duplicate content:** one SQL query using `similarity(discussion, :text) > 0.85`
  (`DUPLICATE_SIMILARITY_THRESHOLD=0.85`) against reviews of the same product or
  same author, excluding self; return the best match id.
- Performance: signals are computed only for the queue payload (≤100 items) and per
  item cost is 3 bounded queries; acceptable. Do NOT compute on public endpoints.
- **Deferred (documented, not built):** photo pHash reverse-image (needs Supabase
  Storage ingestion — M3), submission-IP capture (privacy assessment first).

### Tests
Trgm migration applies on local+Supabase · near-duplicate discussion flags with the
right `duplicate_of` · collusion flags on a constructed mutual-upvote fixture and
not below thresholds · velocity flag on a burst fixture · queue payload carries
`signals` and public endpoints do NOT.

---

## Slice 6 — Commission CSV reconciliation + tier-based revenue split

**Goal:** the §3.3 manual CSV import, idempotent, with the split driven by the
reviewer's membership tier.

### Schema (migration `0008_commission_tier_snapshot`)
- Add to `commissions`: `reviewer_tier` (existing `membership_tier` enum, NULL) and
  `reviewer_share_bps` int NULL — **snapshot at reconciliation time** (immutable
  audit, same principle as vote snapshots).

### CSV contract (pinned)
Header (exact, case-insensitive): `click_ref,order_ref,gross_amount,currency,
order_status,platform`. `click_ref` OR `order_ref` required per row; `gross_amount`
decimal > 0; `currency` = PHP (else row invalid); `platform` ∈ shopee|lazada|amazon.
`row_reference` = `{line_number}` in file; `csv_source` = `{filename}:{sha256[:12]}`
of the file bytes.

### Endpoint
`POST /api/v1/admin/commissions/import` (moderator, multipart file field `file`):
1. Parse + validate **every** row first. Any invalid row → `422` problem+json with
   `errors: [{line, issue}]` and **nothing imported** (all-or-nothing per file —
   the "no silent partial success" rule, resolved strictly).
2. Match each row to a `sessions` row by `click_ref` first, else `order_ref`
   (unmatched rows are **valid but skipped**, reported in the response as
   `unmatched: [line...]` — commissions require attribution).
3. For each match: skip if `(csv_source, row_reference)` already exists
   (idempotent re-upload → `skipped_duplicates` count); else create `commissions`
   row via `split_commission_tiered` (below) with `review_id`/`reviewer_id` from
   the session, `cycle_month = date_trunc('month', session.clicked_at)`,
   snapshot `reviewer_tier`+`reviewer_share_bps`; set session
   `conversion_status=converted`, `order_ref` backfilled; credit
   `users.wallet_balance += reviewer_share` in the same transaction.
4. Audit log (`csv_import`, context: filename, rows, imported, skipped, unmatched).
5. Response: `{imported, skipped_duplicates, unmatched, total_rows}`.
- Run **inline** (monthly exports are small); keep the Celery task
  `reconcile_commission_csv` delegating to the same service function for future
  async use (body: load a stored file by import id — leave NotImplemented guard
  removed only if trivial; acceptable to keep inline-only and document).

### Tier-based split (extend `app/services/earnings.py`, pinned)
`split_commission_tiered(gross, reviewer_share_bps) -> {gross, platform, reviewer,
honesty_fund, ...}`: honesty_fund = 30% **fixed** (capstone invariant); reviewer =
gross × bps/10000 (tier config: standard 3000, founding 3500, special 4000);
platform = remainder (absorbs rounding; sum ALWAYS equals gross to the centavo).
Reviewer bps read from `membership_tiers` config row for the reviewer's tier
(fallback 3000 if missing). Constraint: reject import if any tier bps > 7000
(platform share would go negative) — config sanity check at import time, 422.

### Tests
Split arithmetic per tier sums exactly (param cases incl. 0.01) · full import flow:
create clicks via `/r/{id}`, build a CSV with their click_refs, import → commissions
+ wallet credited + session converted · re-import same file → all skipped, wallet
unchanged (idempotency) · malformed row → 422 + nothing imported · unmatched
reported · bps snapshot recorded · RBAC 403.

---

## Slice 7 — Token economy (data models + transaction history)

**Goal:** append-only token ledger + balances + admin grant, with ONE production
earning hook (publish) proving the pipeline. Spending rules & request-board rewards
are **M3** — do not invent them now.

### Schema (migration `0009_tokens`)
- `users.token_balance` int NOT NULL default 0.
- Table `token_transactions` (append-only; no UPDATE/DELETE endpoints ever):
  `id` UUID PK · `user_id` FK users CASCADE · `amount` int (±, ≠0) ·
  `balance_after` int · `kind` new enum `token_kind`
  (`earn_review_published`, `earn_commission`, `admin_grant`, `admin_deduct`,
  `adjustment`) · `ref_type` str NULL + `ref_id` UUID NULL (polymorphic, e.g.
  review) · `note` text NULL · `created_by` FK users SET NULL · `created_at`.
  Index (`user_id`, `created_at desc`). Partial idempotency guard: unique index
  `uq_token_once (user_id, kind, ref_id) WHERE ref_id IS NOT NULL AND kind LIKE
  'earn_%'` — a given review/commission can award once.
- RLS: NO public select (own-rows only would need auth context; backend-enforced —
  enable RLS with **no** permissive policy, like `sessions`).

### Service (`app/services/token_service.py`)
`grant(db, user_id, amount, kind, ref_type=None, ref_id=None, note=None,
created_by=None)`: lock the user row (`SELECT ... FOR UPDATE`), reject if
`balance + amount < 0` (409 `insufficient_tokens`), insert ledger row with
`balance_after`, update `users.token_balance`, same transaction. Idempotent for
earn kinds via the unique index (catch IntegrityError → no-op).

### Earning hooks (pinned amounts, env-tunable)
- `TOKENS_ON_REVIEW_PUBLISHED: int = 10` — awarded in `referral_service`
  attach_link_and_publish AND publish_without_link (first publish only — the
  idempotency index handles re-publish after unpublish).
- `TOKENS_ON_COMMISSION: int = 25` — awarded per reconciled commission (slice 6
  integration; kind `earn_commission`, ref = commission id).

### Endpoints
`GET /api/v1/tokens/balance` (own) · `GET /api/v1/tokens/transactions` (own,
paginated `limit≤100/offset`) · `POST /api/v1/admin/users/{id}/tokens`
`{amount:int≠0, note:str required}` (moderator; kind admin_grant/admin_deduct by
sign; audit implicit via created_by + note).

### Tests
Publish awards exactly once (unpublish→republish doesn't double-award) · admin
grant/deduct · deduct below zero 409 · ledger balance_after chain consistent ·
transactions endpoint shows own only (other user's token 403/empty) · idempotent
commission award.

---

## Slice 8 — Celery job bodies: PII retention + Honesty Fund distribution

**Goal:** replace the two remaining M0 stubs with real, tested logic.

### PII retention (`run_pii_retention`, daily 03:00 — schedule exists)
- New setting `PII_HASH_SALT: str = ""` — **required non-empty in production**
  (add to `production_issues()`); default dev value `"dev-pii-salt"`.
- Sweep `sessions` using existing `services/pii.due_actions` semantics, in bulk SQL
  (not per-row Python): ≥30d → `ip_hash = hash_ip(ip, salt)`, `ip_address=NULL`;
  ≥90d → `ip_hash=NULL`, `user_agent=NULL`. Service function
  `run_retention_sweep(db) -> {hashed, purged}` (unit-testable with frozen rows);
  Celery task calls it and logs counts.

### Honesty Fund (`run_honesty_fund_distribution(cycle_month)`, monthly 1st 02:00)
- `cycle_month` default = previous calendar month (Asia/Manila).
- Pool = Σ `commissions.honesty_fund_share` where `cycle_month` matches. Pool 0 →
  log + exit.
- Eligible = published, not-removed reviews with `earn_eligible_status =
  honesty_fund`.
- **Honesty Score (pinned):** `trust_weighted_helpful = Σ gate_vote_weight(voter.trust_stage,
  voter.reputation_score, voter_account_age_days, voter.is_on_probation)` over the
  review's **up** votes (existing fn); score = `honesty_score(trust_weighted_helpful,
  review.price_paid or 0)` (existing fn; bracket 1.0× when price unknown). Reviews
  with score 0 get no share.
- Payout_i = pool × score_i / Σscores, rounded down to centavo; remainder (dust)
  stays with the pool (documented). Insert `honesty_fund_distributions` rows
  (idempotent: `uq(cycle_month, review_id)` exists — if the cycle already has rows,
  ABORT with a log, don't re-distribute), credit `wallet_balance`, award NO tokens
  (not specced), audit log (`honesty_fund_distribution`, context: cycle, pool,
  recipients).
- Admin trigger endpoint `POST /api/v1/admin/honesty-fund/run` `{cycle_month?:
  "YYYY-MM"}` (moderator) calling the same service synchronously — the moderator
  shouldn't need Celery access to run a cycle.

### Tests
Retention sweep on frozen fixtures (30/90d boundaries; salt determinism) · fund
distribution proportional math on a 3-review fixture with distinct voter trust ·
idempotent second run aborts · pool-zero no-op · admin endpoint RBAC + happy path.

---

## Consolidated new config (all slices)

| Env var | Default | Slice |
|---|---|---|
| `VOTE_RATE_LIMIT_MAX` / window reuses 60s | 30 | 2 |
| `PRODUCT_TRUST_VISIBILITY_THRESHOLD` | 0.0 (off) | 4 |
| `PRODUCT_TRUST_MIN_REVIEWS` | 5 | 4 |
| `SELLER_TRUST_VISIBILITY_THRESHOLD` | 0.0 (off) | 4 |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 0.85 | 5 |
| `TOKENS_ON_REVIEW_PUBLISHED` | 10 | 7 |
| `TOKENS_ON_COMMISSION` | 25 | 7 |
| `PII_HASH_SALT` | "" (required in prod) | 8 |

Existing ADR-004 constants (45d half-life, velocity 10/h, collusion 0.6/≥5,
z=1.96) are reused, not redefined.

## Sequencing & session guide

| Session | Slice | Depends on | Migration |
|---|---|---|---|
| 1 | 2 — voting + Wilson | — | 0005 |
| 2 | 3 — trust wiring | 2 | none |
| 3 | 4 — seller/product trust + thresholds | 2 | 0006 |
| 4 | 5 — fraud signals | 2 (votes for velocity/collusion) | 0007 |
| 5 | 6 — CSV + tiered split | slice 1 (clicks) | 0008 |
| 6 | 7 — tokens | 1 (publish hook), 6 (commission hook — if 6 unmerged, leave hook commented) | 0009 |
| 7 | 8 — Celery bodies | 6 (commissions for the fund) | none |

Each session's opening prompt: *"Implement slice N per
docs/superpowers/specs/2026-07-13-m2-remainder-master-plan.md. Follow the standard
per-slice checklist."*

## Definition of Done for M2 (final session verifies all)

- [ ] All 7 slices merged; migrations 0005–0009 applied to local **and** Supabase
- [ ] Full pytest + ruff green; `api_smoke.py` extended and 100% passing on both envs
- [ ] Every MILESTONES M2 bullet demonstrably works (map each to an endpoint/test)
- [ ] Fraud signals advisory-only, verified by test (no auto-block path exists)
- [ ] `MILESTONES.md` M2 marked done; `ARCHITECTURE_AS_BUILT.md` updated; deviations logged
- [ ] M2 acceptance test plan written (mirror of `M1_TEST_PLAN.md`, both envs)

## Explicitly out of M2 (do not build)

Earn-eligible **gate voting** / effective-n / Post-Seeding activation (capstone
machinery not in the owner's M2) · payouts/PayPal & payment scheduling (M3) ·
request board & dynamic rewards (M3) · token **spending** rules (M3) · scraping
pipeline (M3 — unresolved ToS conflict) · photo pHash & submission-IP capture
(deferred, privacy assessment) · notifications · Q&A.
