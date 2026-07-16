# Milestone 3 — Acceptance Test Plan (run independently)

**Scope:** request board with AI validation + dynamic token rewards · monetized-
review contracts (duration/renewal/buyout) · earnings processing + payout
scheduling by membership tier · affiliate report ingestion (manual CSV) ·
frontend integration readiness · load testing. A tester can execute this without
the dev team. Fill in **Result** (PASS / FAIL) and Notes.

- **Tester:** ______________  **Date:** __________  **Build/commit:** __________
- **Run against BOTH environments:** ☐ Local (`http://localhost:8000`)
  ☐ Supabase-backed (see `M1_TEST_PLAN.md` §0b)
- **Payouts are testable without PayPal** — set `PAYOUT_PROVIDER=manual` and use
  the mark-paid endpoint. No credentials needed anywhere in this plan.

## 0a. Housekeeping when M3 lands

M3 was built and verified against both databases **before** it was pushed, so
while `origin/main` was still M2 the databases sat at `0014_schema_parity` and M2
code could not run Alembic against them. Pushing M3 closes that window
automatically (the code then contains `0010`–`0014`).

**On merge, do these two things:**

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| 0a1 | Delete the "⚠️ TEMPORARY" section at the top of `M2_TEST_PLAN.md` | it no longer applies — Alembic and docker-compose work again on M2's own terms | | |
| 0a2 | `cd backend && alembic current` (local **and** `USE_SUPABASE=true`) | `0014_schema_parity (head)` — no "Can't locate revision" | | |

## 0. Setup

As `M1_TEST_PLAN.md` §0: get `$TOKEN` (user), `$TOKEN2` (second user), and
`$MODTOKEN` (moderator, promoted via SQL). Set `BASE`. Shorthand: `AUTH`, `MH`.

**Get tokens to spend** (the request board needs them): a moderator grants them —
`POST $BASE/api/v1/admin/users/<uid>/tokens {"amount":100,"note":"test"}`.

## Group A — Request board (slice 9)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| A1 | `POST /api/v1/requests {"title":"Review this fan","details":"<40+ chars>","bounty":25}` | 201, `status:"open"`, `effective_reward:25`, `ai_validation.valid:true`; your token balance drops by 25 (escrow) | | |
| A2 | Post with `"details":"pls"` | 422 `request_invalid` with `reasons[]` explaining the minimum detail | | |
| A3 | Post with `bounty` below `REQUEST_MIN_BOUNTY` (10) | 422 `bounty_below_minimum` | | |
| A4 | Post a bounty larger than your balance | 409 `insufficient_tokens`; nothing created | | |
| A5 | `POST /requests/{id}/upvote` as **$TOKEN2** | 200, `upvote_count:1`, `effective_reward` = bounty + 2 | | |
| A6 | Up-vote your own request | 409 `cannot_upvote_own_request` | | |
| A7 | Up-vote twice as the same user | 409 `already_upvoted` | | |
| A8 | Up-vote from many users | `effective_reward` stops rising at bounty + `REQUEST_TOPUP_CAP` (50) | | |
| A9 | `GET /requests?sort=reward` | higher `effective_reward` first | | |
| A10 | Fulfill with an **unpublished** review | 409 `review_not_published` | | |
| A11 | Fulfill with **someone else's** review | 409 `not_review_author` | | |
| A12 | Fulfill with your own **published** review (`POST /requests/{id}/fulfill {"review_id":...}`) | 200 `status:"fulfilled"`; your balance rises by bounty + top-up | | |
| A13 | Fulfill again | 409 `request_not_open` | | |
| A14 | `DELETE /requests/{id}` on an open request | 200 `cancelled`; escrow refunded exactly | | |
| A15 | `POST /admin/requests/{id}/remove {"reason":"spam"}` as mod | 200 `removed`; requester refunded; request 404s publicly | | |
| A16 | Same as non-moderator | 403 | | |
| A17 | (DB) Set an open request's `expires_at` to the past, run Celery `expire_requests` | `expired`; escrow refunded | | |

## Group B — Contracts (slice 10)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| B1 | Monetize a review (attach a referral link) | a contract is auto-created: `GET /api/v1/contracts` shows it `active`, `term_months:6`, `auto_renew:true` | | |
| B2 | Revoke the link, then re-attach | the **same** contract id is reused (no new term) | | |
| B3 | `PATCH /contracts/{id}/auto-renew {"auto_renew":false}` | 200 | | |
| B4 | (DB) Backdate `expires_at`, run Celery `sweep_contracts` | `auto_renew:true` → renews (`renewal_count`+1, still `active`); `false` → `expired` | | |
| B5 | Import a commission for a review whose contract is **expired** | commission has `reviewer_share_bps:0`, `reviewer_share:0.00`, `contract_status:"expired"`; `honesty_fund_share` still 30%; platform takes the rest; wallet unchanged | | |
| B6 | Same for an **active** contract | `reviewer_share_bps:3000`, wallet credited | | |
| B7 | `POST /admin/contracts/{id}/buyout {"amount":"500.00"}` as mod | 200, offer pending | | |
| B8 | Offer again while pending | 409 `buyout_already_pending` | | |
| B9 | Offer as a non-moderator | 403 · amount `0` → 422 | | |
| B10 | `POST /contracts/{id}/buyout/accept` as the owner | 200 `bought_out`; wallet +500.00 **once** (accept again → 409) | | |
| B11 | Accept as a different user | 403 | | |
| B12 | On a fresh contract: offer then `POST …/buyout/reject` | contract stays `active`, offer cleared, no money moved; a new offer can follow | | |
| B13 | Import a commission after a buyout | reviewer share 0 | | |

## Group C — Payouts (slice 11)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| C1 | `PATCH /api/v1/auth/me/payout-account {"payout_account":"not-an-email"}` | 422 | | |
| C2 | Same with a valid email | 200 | | |
| C3 | Give users ≥ ₱300 wallet (via commission import or Honesty Fund), then `POST /admin/payouts/run {}` as mod | payouts created for users with a payout account AND ≥ `PAYOUT_MIN_PHP`; each user's wallet drops to 0 (money **reserved**) | | |
| C4 | A user with ≥300 but **no** payout account | skipped; counted in `skipped_no_payout_account`; wallet untouched | | |
| C5 | A user below ₱300 | not scheduled | | |
| C6 | Ordering | special → founding → standard (tier `payout_priority`) | | |
| C7 | Run the scheduler again the same month | no double-schedule, no double-debit | | |
| C8 | `GET /api/v1/payouts` | your own only; another user sees none | | |
| C9 | `POST /admin/payouts/{id}/mark-paid {"provider_ref":"REF"}` | 200 `paid`, `paid_at` set; wallet stays debited; second call → 409 | | |
| C10 | `POST /admin/payouts/{id}/fail {"reason":"bad account"}` | 200 `failed`; **wallet refunded** | | |
| C11 | `POST /admin/payouts/{id}/retry` on a failed payout | `scheduled` again; wallet re-reserved | | |
| C12 | `POST /admin/payouts/{id}/cancel` on a scheduled payout | `cancelled`; wallet refunded; second cancel → 409 | | |
| C13 | Any admin payout call as a normal user | 403 | | |
| C14 | With `PAYOUT_PROVIDER=paypal_sandbox` but no credentials | batch stays `scheduled` with a clear log — **not** a crash; manual rail still works | | |

## Group D — Affiliate report ingestion (slice 12)

Use the real fixtures: `backend/tests/fixtures/shopee_commission_report.csv` and
`lazada_conversion_report.csv`.

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| D1 | Import the Shopee fixture | 200, `format:"shopee_commission_report"`; pending/cancelled/zero rows appear in `skipped_unpayable` with reasons — never paid | | |
| D2 | Import the Lazada fixture (**cp1252, not UTF-8**) | 200, `format:"lazada_conversion_report"` — accepted, not rejected for encoding | | |
| D3 | Both fixtures as-is | `imported:0`, every payable row in `unmatched` — they carry no sub-ID, so nobody is paid (correct) | | |
| D4 | `GET /admin/review-queue` | each card has `suggested_sub_id` (e.g. `blt_…`) | | |
| D5 | Attach a link with that `sub_id`, then import a report row carrying it in `Sub_id1` | `imported:1` — the row is attributed and the reviewer credited | | |
| D6 | Attach a link whose URL lacks the sub-ID | response `sub_id_in_url:false` (a warning that its commissions will come back unmatched) | | |
| D7 | Import a file with an unknown header | 422 `csv_invalid` / `unrecognised_report_header`; nothing imported | | |
| D8 | Re-import the same file | all rows `skipped_duplicates`; no double payment | | |
| D9 | Confirm no scraping exists: `grep -ri "scrapy\|selenium\|playwright\|proxy_rotation" backend/app` | no hits | | |

## Group E — Frontend readiness (slice 13)

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| E1 | Open `$BASE/docs` | every endpoint tagged and summarised | | |
| E2 | `cd backend && python -m scripts.export_openapi` then `git diff docs/openapi.json` | no diff (the committed spec is current) | | |
| E3 | `npm run gen:api` then `git diff lib/api-types.d.ts` | no diff (types are in sync) | | |
| E4 | Read `docs/FRONTEND_INTEGRATION.md` | auth flow, error `code` table, page→endpoint map, the sub-ID workflow, and the "never render the raw affiliate URL" rule are all covered | | |
| E5 | Call any endpoint from a browser origin listed in `CORS_ORIGINS` | no CORS error | | |

## Group F — Load & regression

| # | Step | Expect | Result | Notes |
|---|---|---|---|---|
| F1 | `cd backend && pytest -q` | all pass (both environments) | | |
| F2 | `python -m scripts.supabase_verify` | all checks pass, incl. the whole-DB financial invariants | | |
| F3 | `python -m scripts.api_smoke --base-url $BASE --concurrency` | all pass, 0 server errors | | |
| F4 | `locust -f loadtest/locustfile.py --host $BASE --users 100 --spawn-rate 10 --run-time 5m --headless` | p95 read <500 ms, p95 write <1 s, errors <0.1%, zero 5xx (see `LOADTEST_RESULTS.md`; the moderator queue is a known slow screen) | | |
| F5 | M1 + M2 plans | still pass — no regression | | |
