# M3 Master Implementation Plan (slices 9–14, complete)

**Date:** 2026-07-13 · **Planned on:** Fable 5 (final planning pass — with this,
NO further Fable sessions are needed for M2 or M3) · **Implemented on:** Opus 4.8,
one slice per session, in order. Owner decisions captured 2026-07-13: contracts =
**monetized-review contracts** · payout rail = **PayPal Payouts API, sandbox
first** · frontend = **backend readiness + integration guide** (frontend build is
a separate track) · affiliate data pipeline = **no marketplace scraping ever**;
first-party-reports vs manual-CSV-only is a pending owner choice (slice 12 gate).

**M3 scope** (from `docs/MILESTONES.md`): request board with AI validation +
dynamic reward calculation · earnings processing + payment scheduling by
membership tier · contract duration tracking + renewal/buyout · affiliate
performance data pipeline (de-scoped from scraping, see slice 12) · end-to-end
frontend integration · load testing · production deploy.

**The standard per-slice checklist from
`2026-07-13-m2-remainder-master-plan.md` applies to every slice here too**
(migrations reversible + RLS, config in settings + .env.example, tests +
api_smoke, ruff/pytest green, local AND Supabase, docs + OpenAPI re-export,
advisory-only fraud posture, no scraping). Prerequisite: M2 slices 2–8 merged
(tokens ledger, CSV import, votes) — the sequencing table flags exact deps.

---

## Slice 9 — Request board with AI validation + dynamic token rewards

**Concept:** a user posts a "please review this product" request with a **token
bounty** (escrowed from their balance). The community can upvote requests (raising
a platform top-up). A reviewer fulfills it by linking their review; when that
review is **published by the moderator** (existing gate), the escrow + top-up pay
out to the reviewer. AI validation screens requests at creation.

### Schema (migration `0010_request_board`)
- `review_requests`: `id` PK · `request_id` str unique (`req_…`) · `requester_id`
  FK users CASCADE · `product_id` FK products SET NULL (optional) · `title`
  str(200) · `details` text · `source_url` text NULL (marketplace link, never
  fetched) · `bounty` int (tokens escrowed) · `status` enum `request_status`:
  `open | fulfilled | cancelled | expired | removed` · `fulfilled_by_review_id` FK
  reviews SET NULL · `expires_at` timestamptz (now + `REQUEST_TTL_DAYS=30`) ·
  `upvote_count` int default 0 · `ai_validation` JSONB (verdict + reasons) ·
  timestamps. Indexes: status, expires_at. RLS public SELECT.
- `request_upvotes`: request FK CASCADE, user FK CASCADE, `UNIQUE(request_id,
  user_id)`, created_at. RLS public SELECT.
- New `token_kind` enum values (autocommit block): `spend_request_escrow`,
  `earn_request_reward`, `refund_request_escrow`, `platform_topup`.

### Reward math (pinned, env-tunable)
- `REQUEST_MIN_BOUNTY=10` tokens (≤ requester balance; escrowed at creation via
  token_service — kind `spend_request_escrow`, ref=request).
- **Dynamic reward** = `bounty + min(REQUEST_TOPUP_PER_UPVOTE(2) × upvote_count,
  REQUEST_TOPUP_CAP(50))`. Top-up is **minted by the platform** at fulfillment
  (kind `platform_topup` credited to reviewer alongside `earn_request_reward` for
  the bounty). Exposed as computed `effective_reward` in responses.

### AI validation (blocking at creation)
Reuse the ADR-013 provider abstraction with a new prompt path
`validate_request(title, details)` → `{valid: bool, reasons: [str]}`. Stub
heuristic (default, deterministic): invalid if `len(details) < 30` chars, or
title/details are identical, or contains a URL in `details` other than
source_url's host. Claude/OpenAI providers use a strict-JSON prompt mirroring the
critique one. Invalid → `422 request_invalid` with reasons; result stored in
`ai_validation` either way.

### Endpoints
| Method & path | Auth | Behavior |
|---|---|---|
| `POST /api/v1/requests` | user | Validate (AI) → escrow bounty (409 `insufficient_tokens`) → create `open`. |
| `GET /api/v1/requests?status=open&sort=reward\|newest` | public | List; `reward` sorts by effective_reward desc. limit≤100. |
| `GET /api/v1/requests/{id}` | public | Detail incl. effective_reward. |
| `POST /api/v1/requests/{id}/upvote` · `DELETE …/upvote` | user | One per user; not own request (409); rate-limit bucket `vote`. |
| `POST /api/v1/requests/{id}/fulfill` `{review_id}` | user | Review must be OWN, for the same product when request has one, and **published** (else 409 `review_not_published`). Sets `fulfilled`, pays bounty + top-up to reviewer, closes. One fulfillment ever. |
| `DELETE /api/v1/requests/{id}` | requester | Cancel while `open` → refund escrow (`refund_request_escrow`). |
| `POST /api/v1/admin/requests/{id}/remove` `{reason}` | moderator | Remove + refund requester; audit-log. |
- Daily Celery `expire_requests` (05:30): `open` past expires_at → `expired` +
  refund escrow.
- **Fulfillment-on-publish nicety:** if a review submitted for a request gets
  published later, fulfillment stays a manual `POST /fulfill` by the reviewer
  (explicit claim; avoids ambiguous auto-matching). Document this.

### Tests
Escrow debits + cancel refunds + expiry refunds (ledger chain) · insufficient
balance 409 · AI stub rejects short details (422 with reasons) · upvote
uniqueness/self-block · fulfill guards (not-own review, unpublished, wrong
product) · reward math incl. top-up cap · moderator remove refunds · RBAC.

---

## Slice 10 — Monetized-review contracts (duration / renewal / buyout)

**Concept:** every monetized review runs a revenue-share **contract**. While
active, commissions split per tier (M2 slice 6). At term end it auto-renews
unless disabled; the platform may **buy out** the reviewer (one-time PHP wallet
credit) after which the reviewer's share stops.

### Schema (migration `0011_review_contracts`)
- `review_contracts`: `id` PK · `review_id` FK reviews CASCADE · `reviewer_id` FK
  users SET NULL · `status` enum `contract_status`: `active | expired |
  bought_out` · `started_at` · `term_months` int (default
  `CONTRACT_TERM_MONTHS=6`) · `expires_at` · `auto_renew` bool default true ·
  `renewal_count` int default 0 · buyout: `buyout_offer_amount` Numeric(12,2)
  NULL, `buyout_offered_at/by`, `buyout_accepted_at`, `buyout_rejected_at` ·
  timestamps. **Partial unique:** `UNIQUE(review_id) WHERE status='active'`.
  RLS public SELECT.

### Lifecycle (pinned)
- **Creation:** automatically in `attach_link_and_publish` (slice 1 hook) when a
  review first becomes monetized; **re-attach after revoke reuses the existing
  active contract** if one exists, else creates one.
- **Daily Celery `sweep_contracts` (05:00):** for `active` past `expires_at`:
  `auto_renew` → `expires_at += term_months`, `renewal_count++` (stays `active`);
  else → `expired`.
- **Economic effect (single integration point):** M2 slice-6
  `split_commission_tiered` consults the review's contract at reconciliation:
  `active` → reviewer tier bps; `expired`/`bought_out`/none → **reviewer bps = 0**
  (their share goes to platform; honesty fund 30% unchanged). Snapshot
  `contract_status` onto the commission row (add col in this migration:
  `commissions.contract_status` NULL).
- **Buyout flow:** moderator offers a PHP amount → pending offer (one at a time;
  409 if pending). Reviewer **accepts** → wallet credited `buyout_offer_amount`,
  status `bought_out`, audit `override` + context; **rejects** → offer cleared,
  contract unchanged. Offers auto-void if the contract expires first.

### Endpoints
`GET /api/v1/contracts` (own) · `PATCH /api/v1/contracts/{id}/auto-renew`
`{auto_renew: bool}` (owner) · `POST /api/v1/contracts/{id}/buyout/accept` ·
`POST /…/buyout/reject` (owner) · moderator: `GET /api/v1/admin/contracts?status=&expiring_within_days=` ·
`POST /api/v1/admin/contracts/{id}/buyout` `{amount}` · all mutations audit-logged.

### Tests
Contract auto-created on monetize (once, incl. re-attach case) · sweep renews vs
expires by flag · expired contract zeroes reviewer share on a CSV import (rerun the
slice-6 flow fixture) · buyout offer/accept credits wallet exactly once and future
import pays 0 bps · reject clears offer · pending-offer 409 · RBAC.

---

## Slice 11 — Earnings processing + payout scheduling by tier (PayPal sandbox)

### Schema (migration `0012_payouts`)
- `payouts`: `id` PK · `payout_id` str unique (`pay_…`) · `user_id` FK CASCADE ·
  `amount` Numeric(12,2) · `currency` 'PHP' · `status` enum `payout_status`:
  `scheduled | processing | paid | failed | cancelled` · `method` enum
  `payout_method`: `paypal_sandbox | paypal_live | manual` · `provider_ref` str
  NULL · `batch_id` str NULL · `scheduled_for` date · `paid_at` NULL ·
  `failure_reason` NULL · timestamps. Index (user_id), (status). RLS: **no public
  policy** (like sessions — financial data).

### Scheduling (pinned)
- Monthly Celery `schedule_payouts` (5th, 02:30 Asia/Manila; also moderator-
  triggerable): select users with `wallet_balance >= PAYOUT_MIN_PHP (300)` AND
  `payout_account` set, **ordered by their tier's `payout_priority`** (special→
  founding→standard; that IS the "by membership tier" scheduling). For each:
  create payout for the full balance, **debit wallet immediately** (reserved),
  `batch_id = "batch_YYYYMM"`. Users without `payout_account` are skipped and
  counted in the audit log.
- `PATCH /api/v1/auth/me/payout-account` `{payout_account: email}` (user) — the
  missing setter; validate email shape.

### Disbursement (adapter seam `app/adapters/paypal.py`)
- `PAYOUT_PROVIDER = paypal_sandbox | paypal_live | manual` (default
  `paypal_sandbox`). PayPal adapter: httpx, OAuth client-credentials
  (`PAYPAL_CLIENT_ID/SECRET`, `PAYPAL_BASE_URL` default
  `https://api-m.sandbox.paypal.com`), Payouts API (`POST /v1/payments/payouts`,
  sender_batch_id = our batch, receiver = payout_account, PHP). Missing creds →
  batch stays `scheduled` + clear log (NOT a crash) — **manual mode always
  available**: moderator `POST /api/v1/admin/payouts/{id}/mark-paid`
  `{provider_ref}`.
- Status flow: `scheduled → processing` (batch submitted) → `paid`
  (`provider_ref` recorded; poll batch status via
  `GET /v1/payments/payouts/{batch}` on a follow-up Celery check or the admin
  refresh endpoint) · `failed` → **wallet refunded** + reason · `cancelled`
  (admin, only while scheduled) → refunded.
- Endpoints: `GET /api/v1/payouts` (own) · moderator: `GET /api/v1/admin/payouts?status=&batch_id=` ·
  `POST /api/v1/admin/payouts/run` (run scheduler now) · `POST /api/v1/admin/payouts/{id}/mark-paid` ·
  `POST /…/retry` · `POST /…/cancel`. All audit-logged (`payout` action exists).
- **Tests mock the adapter** (monkeypatch/respx) — no real PayPal calls in CI.
  End-to-end sandbox verification requires owner-supplied sandbox creds
  (🔒 blocked-on; note in report if unavailable — everything else still verifiable
  via `manual` mode).

### Tests
Scheduler picks ≥300 + account-set only, tier ordering by priority, wallet debited
at schedule · failure refunds · cancel refunds · mark-paid manual path · adapter
called with correct payload (mocked) · own-payouts visibility · RBAC · idempotent
scheduler (re-run same month doesn't double-schedule a user with 0 balance).

---

## Slice 12 — Affiliate performance ingestion (DECISION GATE — ask first)

**Open the session by asking the owner ONE question:** *"First-party report
automation, or keep manual CSV only?"* Then:

- **Path A — manual CSV only:** no code. Update MILESTONES (item resolved as
  manual-by-design), MARKETPLACE_INTEGRATION.md, close the slice.
- **Path B — first-party automation (compliant):** ingest ONLY reports the owner
  is authorized to access from their own affiliate accounts. Build:
  `REPORT_FETCH_URL` + `REPORT_FETCH_AUTH_HEADER` env (authenticated report
  export URL if the program provides one) · monthly Celery `fetch_affiliate_report`
  (2nd, 03:00) → download → feed the **existing** slice-6 import service (same
  validation/idempotency/audit) · failures alert via log + audit row · admin
  `POST /api/v1/admin/commissions/fetch-now`. If the program offers no export URL,
  Path B degrades to the manual upload endpoint — document and close.
- **Hard rule either way: no marketplace-page scraping, no proxies, no headless
  browsers.** (Owner has already excluded these.)

---

## Slice 13 — Frontend integration readiness

No frontend pages are built (owner decision). Deliver everything the Next.js app
needs:
1. **OpenAPI completeness pass:** every router documents its problem responses
   (reuse the `PROBLEM_RESPONSES` pattern from auth); verify all routes tagged;
   re-export `docs/openapi.json`.
2. **TypeScript types for the frontend:** `npx openapi-typescript
   docs/openapi.json -o src/lib/api-types.d.ts` (add as `npm run gen:api` in the
   root package.json; commit the generated file).
3. **`docs/FRONTEND_INTEGRATION.md`:** auth flow (register/login → Bearer token,
   expiry/401 handling) · page→endpoint map (listing `?sort=wilson`, product page
   + trust/low_trust, submit review → "awaiting moderator" state
   (`published_at:null`), my drafts, `/r/{id}` rule (**never render the raw
   affiliate URL — it isn't exposed**), moderator queue + one-card workflow,
   tokens balance/history, request board, contracts, payouts) · problem+json
   error contract with the `code` registry · required envs
   (`NEXT_PUBLIC_API_URL`, existing Supabase publishable vars) · CORS setup note
   (`CORS_ORIGINS`).
4. **CORS check:** confirm `CORS_ORIGINS` env round-trips (add the deployed
   frontend origin placeholder to `.env.example`).

Tests: OpenAPI export has 0 untagged routes + problem schema present; a small
script check that `api-types.d.ts` is in sync (regenerate → git diff clean).

---

## Slice 14 — Load testing + production deploy + M3 acceptance (final)

1. **Load test (bounded, not M3-inflating):** add `locust` to dev requirements +
   `backend/loadtest/locustfile.py`: mix 70% `GET /reviews?sort=wilson` + product
   pages, 15% auth'd browse (`/me`, tokens), 10% review submit, 5% moderator
   queue. **Targets (pinned):** at 100 concurrent users, 5-min run: p95 read
   < 500 ms, p95 write < 1 s, error rate < 0.1%, zero 5xx. Run vs local compose,
   then a **capped** run (25 users, 3 min) vs the Supabase-backed instance
   (protect the pooler). Record results in `docs/LOADTEST_RESULTS.md`; if targets
   miss, tune `--workers`/pool per PRODUCTION.md budget and re-run (that's the
   whole remediation loop — deeper perf work would be a new owner conversation).
2. **Production deploy:** execute `docs/PRODUCTION.md` on the owner's chosen host
   (🔒 owner supplies host + secrets at session time): `APP_ENV=production`,
   Supabase pooler, managed Redis, `ENABLE_DOCS=false`, real `CORS_ORIGINS`,
   release-step migration, then `python -m scripts.api_smoke --base-url
   https://<prod>` full pass. Confirm Supabase PITR/backups on, and the daily
   PII-retention beat is running.
3. **M3 acceptance test plan:** write `docs/M3_TEST_PLAN.md` mirroring the
   M1 plan's format (both-environments rule included), covering request board,
   contracts, payouts (manual mode so testers don't need PayPal), and the
   integration guide walkthrough.
4. Mark M3 done in `MILESTONES.md`; final `ARCHITECTURE_AS_BUILT.md` +
   `DEVIATIONS.md` pass.

---

## Consolidated new config (M3)

| Env var | Default | Slice |
|---|---|---|
| `REQUEST_MIN_BOUNTY` / `REQUEST_TOPUP_PER_UPVOTE` / `REQUEST_TOPUP_CAP` / `REQUEST_TTL_DAYS` | 10 / 2 / 50 / 30 | 9 |
| `CONTRACT_TERM_MONTHS` | 6 | 10 |
| `PAYOUT_MIN_PHP` (exists as constant — promote to setting) | 300 | 11 |
| `PAYOUT_PROVIDER` | paypal_sandbox | 11 |
| `PAYPAL_CLIENT_ID` / `PAYPAL_SECRET` / `PAYPAL_BASE_URL` | "" / "" / sandbox URL | 11 |
| `REPORT_FETCH_URL` / `REPORT_FETCH_AUTH_HEADER` | "" (Path B only) | 12 |

## Sequencing & dependencies

| Session | Slice | Depends on | Migration |
|---|---|---|---|
| 8 | 9 — request board | M2 slice 7 (tokens) | 0010 |
| 9 | 10 — contracts | slice 1; M2 slice 6 (split hook) | 0011 |
| 10 | 11 — payouts | M2 slice 6 (wallet inflows) | 0012 |
| 11 | 12 — ingestion gate | M2 slice 6 | none |
| 12 | 13 — frontend readiness | all API surface stable | none |
| 13 | 14 — load test + deploy + acceptance | everything | none |

🔒 **External blockers to raise with the owner when reached:** PayPal sandbox
credentials (slice 11 live verification) · slice-12 Path decision · production
host + secrets (slice 14).

## Definition of Done for M3

- [ ] Slices 9–14 merged; migrations 0010–0012 on local **and** Supabase
- [ ] Load-test targets met and recorded; production deployed and smoke-passed
- [ ] `M3_TEST_PLAN.md` delivered; MILESTONES M3 marked done
- [ ] No scraping code anywhere; fraud/marketplace posture unchanged

## Out of scope (all milestones complete ≠ these exist)

GCash/Maya (RA 11967 registrations) · NLP standardization · AI moderation ·
multi-moderator tooling · native apps · Q&A · gate voting/Post-Seeding — all
per the original M5/out-of-scope lists; new work beyond M3 needs a new owner
conversation (and may be planned on whatever model policy then applies).
