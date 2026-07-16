# Milestone 2 — Acceptance Test Plan (run independently)

**Scope:** M2 Reputation & Trust — community voting + Wilson ranking, trust
progression + badges, seller reviews + product/seller trust ratings + visibility
thresholds, fraud signals (advisory), commission CSV reconciliation + tier-based
split, token economy, Honesty Fund + PII retention jobs. A tester can execute this
end-to-end against a running backend without the dev team. Fill in the **Result**
column (PASS / FAIL) and Notes.

- **Tester:** ______________  **Date:** __________  **Build/commit:** __________
- **Run this plan against BOTH environments** (tick each when complete):
  ☐ **Local** (`http://localhost:8000`)  ☐ **Supabase-backed** (see M1 plan §0b — **required**)


---

## 0. Setup

Same as `M1_TEST_PLAN.md` §0/§0b: get a normal-user token (`$TOKEN`), a second
user token (`$TOKEN2`, the "voter"), and a moderator token (`$MODTOKEN`; promote
via SQL). Set `BASE`. All bodies are JSON unless noted. Shorthand:
`AUTH='Authorization: Bearer '$TOKEN` etc.

**Seed a published review** (used throughout Group A–C):
```bash
# author ($TOKEN) creates a product + a verified review, moderator publishes it
PID=$(curl -s -X POST $BASE/api/v1/products -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"M2 Test Widget","category":"electronics"}' | jq -r .id)
RID=$(curl -s -X POST $BASE/api/v1/reviews -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"product_id\":\"$PID\",\"title\":\"Solid\",\"discussion\":\"Weeks of use.\",
       \"verdict\":\"yes_absolutely\",\"star_rating\":4,\"photo_url\":\"https://example.com/p.jpg\"}" | jq -r .id)
curl -s -X POST $BASE/api/v1/admin/reviews/$RID/publish -H "$MODAUTH"
```

## Group A — Community voting + Wilson ranking (slice 2)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| A1 | `POST /api/v1/reviews/$RID/vote {"vote":"up"}` as **$TOKEN2** | 200; `helpful_votes:1`; `wilson_score > 0` | | |
| A2 | Repeat A1 with `{"vote":"down"}` | 200; `helpful_votes:0, unhelpful_votes:1` (upsert, not a 2nd vote) | | |
| A3 | `DELETE /api/v1/reviews/$RID/vote` as $TOKEN2 | 200; both counters 0; `wilson_score` 0 | | |
| A4 | Vote as the **author** ($TOKEN) | 409 `cannot_vote_own_review` | | |
| A5 | Vote with **no token** | 401 | | |
| A6 | Vote on an **unpublished** review (submit one, don't publish) | 404 | | |
| A7 | `DELETE .../vote` when you have no vote | 404 `vote_not_found` | | |
| A8 | Up-vote $RID from 3 fresh users, then `GET /api/v1/reviews?product_id=$PID&sort=wilson` | the up-voted review ranks above un-voted ones | | |
| A9 | > 30 votes in 60s from one IP | 429 `rate_limited` | | |

## Group B — Trust progression (slice 3)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| B1 | `GET /api/v1/users/<author-id>/trust` (public, no auth) | 200; shape: trust_stage, trust_level_name, reputation_score, verified_review_count, helpfulness_ratio, badges[] | | |
| B2 | After the seed publish (verified review) | `trust_stage: 2`, name "Verified Buyer", `verified_review_count: 1`, badge `verified_buyer` present exactly once | | |
| B3 | Publish a 2nd verified review by the same author | still exactly one `verified_buyer` badge | | |
| B4 | After A8's up-votes | `helpfulness_ratio: 100`; reputation_score rises (60 helpfulness pts + volume pts) | | |
| B5 | Confirm there is **no** endpoint to set trust_stage directly (check `/docs`) | none exists | | |

## Group C — Seller reviews, trust ratings, thresholds (slice 4)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| C1 | `PATCH /api/v1/users/<uid>/role {"role":"seller"}` as user | 403 | | |
| C2 | Same as moderator | 200, role seller; `moderation_logs` gets an `override` row | | |
| C3 | Same with `{"role":"moderator"}` | 422 `role_not_grantable` | | |
| C4 | `POST /api/v1/sellers/<seller-id>/reviews` (body: accuracy, order_completeness, customer_service 1-5, packaging_quality 1-5, overall_rating 1-5, would_recommend) | 201; visible immediately in `GET /sellers/<id>/reviews` | | |
| C5 | Repeat C4 same reviewer | 409 `seller_review_exists` | | |
| C6 | Review **yourself** as a seller | 409 | | |
| C7 | Review a non-seller user | 404 `seller_not_found` | | |
| C8 | `GET /api/v1/sellers/<seller-id>` | 200; seller_trust_score set; accuracy_pct/completeness_pct/customer_service_avg/packaging_avg/recommend_pct match the submitted reviews | | |
| C9 | `GET /api/v1/products/$PID` | carries `trust_score` (>0 after a ≥4★ published review) and `low_trust:false` | | |
| C10 | Set `PRODUCT_TRUST_VISIBILITY_THRESHOLD=0.5`, `PRODUCT_TRUST_MIN_REVIEWS=1`, restart; list products | a product whose only published review is ≤3★ disappears from `GET /products`, still 200 by id with `low_trust:true`; `?include_low_trust=true` shows it | | |
| C11 | Reset thresholds to 0 | listing shows everything again | | |

## Group D — Fraud signals (slice 5; ADVISORY ONLY)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| D1 | Submit two reviews with near-identical `discussion` (same product) then `GET /api/v1/admin/review-queue` | the queue card's `signals.duplicate_content: true` with `duplicate_of` = the other review's id | | |
| D2 | Queue card for a fresh author | `signals.author_account_age_days` ≈ 0, `author_review_count` correct | | |
| D3 | `GET /api/v1/reviews/<id>` (public) | **no** `signals` field anywhere | | |
| D4 | Flagged review | stays published/visible — nothing is auto-blocked | | |

## Group E — Commission CSV + tiered split (slice 6)

```csv
click_ref,order_ref,gross_amount,currency,order_status,platform
<paste a real click_ref>,ORD-1,100.00,PHP,completed,shopee
```
Get a real `click_ref`: attach a referral link to $RID (see M1/M2-slice-1 flow),
hit `GET $BASE/r/$RID` once, then read it from the `sessions` table.

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| E1 | `POST /api/v1/admin/commissions/import` (multipart `file`) as moderator | 200 `{imported:1, skipped_duplicates:0, unmatched:[], total_rows:1}` | | |
| E2 | Author's wallet | +30.00 (standard tier 3000 bps of 100.00); commissions row has reviewer_tier `standard`, reviewer_share_bps 3000, honesty_fund_share 30.00 | | |
| E3 | The matched session | `conversion_status: converted`, order_ref backfilled | | |
| E4 | Re-upload the SAME file | `imported:0, skipped_duplicates:1`; wallet unchanged | | |
| E5 | File with any malformed row (e.g. gross `abc`) | 422 with `errors:[{line,issue}]`, NOTHING imported | | |
| E6 | Row with an unknown click_ref | valid import, row reported in `unmatched` | | |
| E7 | Import as non-moderator | 403 | | |

## Group F — Token economy (slice 7)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| F1 | After the seed publish | `GET /tokens/balance` (author) = 10 (`TOKENS_ON_REVIEW_PUBLISHED`) | | |
| F2 | Unpublish then re-publish the same review | balance still 10 (no double award) | | |
| F3 | After E1 (commission import) | +25 (`TOKENS_ON_COMMISSION`); re-import (E4) does not add more | | |
| F4 | `GET /tokens/transactions` | newest-first ledger; `balance_after` chain consistent; each earn row carries ref_type/ref_id | | |
| F5 | `POST /api/v1/admin/users/<uid>/tokens {"amount":50,"note":"bonus"}` as mod | 200 kind `admin_grant`; negative amount → `admin_deduct` | | |
| F6 | Deduct more than the balance | 409 `insufficient_tokens` | | |
| F7 | Same call as non-moderator | 403 | | |
| F8 | Confirm there are **no** update/delete endpoints for transactions (check `/docs`) | none exist | | |

## Group G — Honesty Fund + PII retention (slice 8)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| G1 | Publish a ≤2★ verified review (no link) | `earn_eligible_status: honesty_fund` | | |
| G2 | Give it an up-vote from a stage-2+ voter; ensure the cycle has commissions (E1); `POST /api/v1/admin/honesty-fund/run {"cycle_month":"<that cycle>"}` as mod | 200 `{status:"distributed", pool, recipients}`; `honesty_fund_distributions` rows; author wallet credited | | |
| G3 | Run the same cycle again | `status:"already_distributed"`, no new rows/credits | | |
| G4 | Run a cycle with no commissions | `status:"empty_pool"` | | |
| G5 | As non-moderator | 403 | | |
| G6 | (DB) Insert sessions with `clicked_at` 31 and 91 days ago (deadlines via `services/pii.retention_deadlines`), run the Celery task `run_pii_retention` (or call `retention_service.run_retention_sweep`) | 31d row: `ip_address` NULL + `ip_hash` = salted SHA-256; 91d row: ip fields NULL + `user_agent` NULL; fresh rows untouched | | |

## Group H — Regression & automated suite

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| H1 | `cd backend && pytest -q` (against the same DB) | all tests pass | | |
| H2 | `python -m scripts.api_smoke --base-url $BASE --concurrency` | all checks pass; 0 server errors in the burst | | |
| H3 | Full M1 plan Groups A–E | still pass (no regression) | | |
