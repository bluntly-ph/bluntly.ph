# Bluntly.ph — Backend System: Design, Implementation, and Verification

**A Technical Report for the Capstone Manuscript**
Polytechnic University of the Philippines — College of Computer and Information Sciences (PUP CCIS)
Prepared: 2026-07-17 · Backend build status: **M0 + M1 + M2 complete; M3 built and verified, not yet deployed**

---

## Abstract

Bluntly.ph is a web-based verified product- and seller-review platform for Filipino
online shoppers, conceived to remediate six documented failures of the review
systems embedded in dominant Philippine e-commerce marketplaces (no proof-of-purchase
requirement, no completeness standard, no structured seller evaluation, suppression
of negative feedback, and incentives that reward volume over substance). This report
documents the **backend** of that platform: a FastAPI application backed by
PostgreSQL (Supabase) with SQLAlchemy, Alembic, Redis, and Celery. The backend
operationalises the platform's central thesis — *structural incentive alignment* —
by making authentic contributions more visible (time-decayed Wilson-score ranking),
more rewarded (a 40/30/30 affiliate split plus an Honesty Fund that pays honest
negative reviews), and more trusted (proof-of-purchase verification, a seven-layer
fraud-deterrence framework, and human moderation) than inauthentic ones.

The system comprises **24 domain tables** (all row-level-security enabled),
FastAPI-native JWT/OAuth2 authentication with Argon2id password hashing, a governed
OpenAPI contract with an RFC 9457 error format, and a suite of pure, unit-tested
trust/ranking/earnings algorithms. As of this report the backend passes **159
unit/integration tests**, **49/49 end-to-end milestone claims**, and **59/59
schema-and-financial-integrity checks**, each executed against **both** a local
PostgreSQL instance and the live Supabase project. A simulated load test of 100
concurrent users sustained a p95 latency of 73 ms with zero server errors. The
report also records, in the interest of academic honesty, every deviation from the
original specification and the work that remains before public launch.

---

## 1. Introduction and Scope

### 1.1 Purpose of this report
This document describes the backend as **actually built and verified**, not as
originally imagined. Where the build diverges from the source capstone manuscript,
the divergence is stated explicitly (§13) together with the Architecture Decision
Record (ADR) that governs it. The report is intended to be read alongside the
project's living documentation: `docs/ARCHITECTURE_AS_BUILT.md`, `docs/schema.md`,
`docs/DEVIATIONS.md`, the ADRs in `docs/adr/`, and the milestone acceptance plans
(`M1_TEST_PLAN.md`, `M2_TEST_PLAN.md`, `M3_TEST_PLAN.md`).

### 1.2 What the backend is
A single FastAPI service exposing a versioned REST API (`/api/v1`) that implements:
accounts and membership tiers; a product catalogue with URL-based submission and
manual canonicalisation; structured review submission with version history and an
AI critique aid; a moderator-gated publication and affiliate-link flow; community
voting with Wilson-score ranking; a six-stage trust-progression system; seller and
product trust ratings; advisory fraud/collusion signals; commission reconciliation
with a tiered revenue split; a token economy; a bounty-based request board;
revenue-share contracts; membership-tiered payouts; a monthly Honesty Fund; and a
privacy-preserving PII-retention regime. Background computation runs on Celery.

### 1.3 What the backend deliberately is *not*
Consistent with the marketplaces' Terms of Service, the backend contains **no
web-scraping, no headless browsers, and no marketplace API calls**. Every
marketplace touchpoint — product naming, affiliate-link generation, commission
ingestion — is admin-mediated and manual by design. This constraint is not
incidental; it is the reason the platform exists as a manual-first system and is
enforced by an automated test that fails if any scraping dependency ever appears in
the codebase (§12).

---

## 2. Backend Objectives (mapped to the capstone objectives)

| # | Capstone objective (PRD §2) | Backend realisation |
|---|---|---|
| 1 | Proof-of-purchase verification | Photo-at-submission ⇒ `verification_status = verified`; unverified reviews can never be monetised (guard beyond spec, FR-3). |
| 2 | Structured review format | `reviews` enforces discussion, `verdict` (yes_absolutely/it_depends/hard_pass), 1–5 stars, pros/cons (JSONB), title, photo. |
| 3 | Four-dimension seller reviews | `seller_reviews`: accuracy + order_completeness (binary), customer_service + packaging_quality (1–5), overall rating, would-recommend. **Withdrawn 2026-07-28** — see §6.7. |
| 4 | Hybrid incentive model | 40/30/30 split (`constants.py`); six-stage trust; moderator-gated `earn_eligible` routing ≥3★→affiliate, ≤2★→Honesty Fund. |
| 5 | Community Q&A | `questions`/`answers` with buyer/seller routing, Best Answer, First Responder (schema + trust hooks present; UI is a separate track). |
| 6 | Research consolidation | Verified reviews, seller reviews (**withdrawn 2026-07-28**, §6.7), community price observations (`price_history`, 3-observation rule), and product data in one API. |

---

## 3. System Architecture (as built)

### 3.1 Technology stack

| Layer | Choice | Notes |
|---|---|---|
| API framework | FastAPI (synchronous endpoints), Uvicorn (2 workers) | Sync `def` handlers run in Starlette's AnyIO threadpool. |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | 15 migration files; head `0014_schema_parity`. |
| Database | PostgreSQL 16 (local dev) / **Supabase PostgreSQL 17** (ap-southeast-1) | 24 domain tables, all RLS-enabled. |
| Cache / broker | Redis 7 | Rate-limiter store and Celery broker; limiter fails **open** if absent. |
| Background jobs | Celery worker + beat | 8 scheduled tasks (§8), Asia/Manila. |
| Authentication | FastAPI-native JWT/OAuth2, **Argon2id** hashing | ADR-010, ADR-011. |
| AI critique | Provider abstraction (stub / Claude / OpenAI), default no-key stub | ADR-013. |
| Error contract | **RFC 9457** `application/problem+json`, everywhere | Machine-readable `code` on every error. |
| Configuration | pydantic-settings, 12-factor `.env` | Fails fast in production on weak secrets (§10.4). |

### 3.2 Runtime topology

```
                        HTTPS
  Clients ───────────────▶ TLS terminator / load balancer
  (browser, mobile)              │   (health probe: GET /health — DB-free)
                                 ▼
                   ┌──────────────────────────────┐
                   │  Uvicorn (2 workers/container)│
                   │  FastAPI app                  │
                   │   • sync endpoints → AnyIO    │
                   │     threadpool (20 tokens)    │
                   │   • JWT auth, RBAC, RFC 9457  │
                   └───┬───────────┬───────────┬───┘
             SQLAlchemy│   Redis   │           │ https (only if AI_PROVIDER≠stub)
           pool(10+10) │  (limiter,│           │
                       ▼   broker) ▼           ▼
            ┌───────────────┐ ┌────────┐  ┌──────────────┐
            │ PostgreSQL    │ │ Redis 7│  │ Anthropic /  │
            │ Supabase      │ └───┬────┘  │ OpenAI API   │
            │ (RLS, 24 tbls)│     │broker └──────────────┘
            └───────────────┘     ▼
                            Celery worker + beat
```

Supabase is a separate managed service. The backend reaches it over **two
deliberately different connection paths** (§11.1): the application uses the
**transaction pooler** (port 6543, multiplexed); Alembic migrations use the
**session pooler** (port 5432), because `ALTER TYPE … ADD VALUE` requires a real
session that transaction mode cannot provide.

### 3.3 Request lifecycle
1. TLS terminator → Uvicorn worker → FastAPI.
2. The synchronous handler executes in the AnyIO threadpool (ceiling
   `THREADPOOL_TOKENS = 20`, the per-process in-flight cap).
3. `get_db` yields a pooled SQLAlchemy `Session` (`DB_POOL_SIZE + DB_MAX_OVERFLOW =
   10 + 10`, 10 s fail-fast timeout).
4. Auth dependencies validate the HS256 JWT and load the `User`; **RBAC always reads
   `users.role` from the database, never trusting the token claim**, so a promotion
   takes effect immediately without re-login.
5. Handler → service layer → ORM; the response is serialised by a Pydantic schema.
6. Any error is caught by a registered handler and emitted as RFC 9457
   `problem+json` carrying `type, title, status, detail, instance, code[, extra]`.

---

## 4. Identity, Authentication, and Access Control

The original specification left identity ambiguous — it assigned authentication to
*both* Supabase Auth and a Redis-backed session system (Architecture §2, Open
Question Q1). **ADR-010** resolves this in favour of **FastAPI-native identity**:

- **Registration/login:** `POST /auth/register` hashes the password with
  **Argon2id** (ADR-011) and issues an HS256 JWT; `POST /auth/login` uses the
  OAuth2 password form (`username` = email); `GET /auth/me` returns the caller.
- **Token:** HS256, claims `iss = bluntly-ph`, `sub`, `role`, `exp` (default 24 h).
- **RBAC:** `require_role("moderator")` gates every administrative route off the
  **database role**. RLS on Supabase is retained as defense-in-depth for any direct
  (PostgREST) access but is not the primary control, since the backend connects as
  the database owner and enforces authorization in the API layer.
- **Rate limiting:** authentication and voting endpoints use a fixed-window Redis
  limiter (default 10 auth requests / 60 s / IP). When Redis is unreachable the
  limiter **fails open** and logs — an availability-over-strictness choice suitable
  for the evaluation phase.

Passwords are verified in tests to be stored only as Argon2id (`$argon2…`) and never
in plaintext.

---

## 5. Data Model

### 5.1 Overview
The schema is the source of truth in `backend/app/models/` and is migrated by
`backend/alembic/versions/`. The database holds **24 domain tables plus
`alembic_version` (25 public tables), every one RLS-enabled**. Primary keys are
UUIDs (`gen_random_uuid()`); timestamps are `created_at`/`updated_at`; denormalised
aggregates are updated by service-layer transactions rather than DB triggers (a
testability choice, DEVIATIONS §6).

### 5.2 Table inventory

| Domain | Tables |
|---|---|
| **Accounts & reputation** | `users`, `badges`, `user_badges`, `membership_tiers` |
| **Catalogue** | `products`, `product_platforms`, `price_history` |
| **Reviews** | `reviews`, `review_versions`, `review_votes`, `referral_links` |
| **Q&A** | `questions`, `answers` |
| **Seller** | `seller_reviews` — **withdrawn 2026-07-28**, see §6.7 (table drop `0024_drop_seller_reviews` (applied 2026-08-19)) |
| **Attribution & money** | `sessions`, `commissions`, `honesty_fund_distributions`, `token_transactions`, `payouts` |
| **Gate & moderation** | `earn_eligible_votes`, `moderation_logs` |
| **M3 request/contract** | `review_requests`, `request_upvotes`, `review_contracts` |

### 5.3 Notable design decisions
- **`earn_eligible_votes` snapshots** the voter's trust stage, trust score, account
  age, and probation state at vote time, so gate decisions are auditable and immune
  to retroactive trust changes.
- **`sessions`** encodes the PII lifecycle inline: precomputed `ip_hash_at`,
  `ip_delete_at`, and `ua_purge_at` deadlines drive the retention sweep (§9.6).
- **`token_transactions`** is an append-only ledger: it has a `balance_after` chain,
  a partial unique index that makes each earn event idempotent, and **no permissive
  RLS policy** (backend-only). There is no update or delete surface anywhere in the
  API — verified by an OpenAPI assertion.
- **`commissions`** replaces the spec's polymorphic TEXT reference with a typed
  `target_type` enum and real `review_id`/`answer_id` FKs under a CHECK constraint,
  restoring referential integrity (DEVIATIONS §3), and snapshots the reviewer's tier
  and share-bps at reconciliation.
- **`referral_links`** enforces one active link per review via a partial unique
  index `UNIQUE(review_id) WHERE status='active'`; the raw affiliate URL is never
  exposed in any API body (§6.3).

### 5.4 Enumerated types
Enums are first-class PostgreSQL types, including `member_role`, `platform`
(shopee/lazada/**amazon**/other), `verdict`, `verification_status`,
`earn_eligible_status` (none/pending/approved/rejected/monetized/honesty_fund),
`vote_direction`, `token_kind` (9 values), and `request_status` (5 values). The
platform-enum extension to Amazon and the token/request enums were added in M2/M3.

---

## 6. Functional Subsystems

### 6.1 Accounts and membership tiers (M1)
Three membership tiers — **Special, Founding, Standard** — are configured in
`membership_tiers` (`revenue_share_bps`, `payout_priority`, `benefits` JSONB). Tier
management is moderator-gated. Membership tier is distinct from the trust stage: the
former sets economic terms (revenue share, payout order), the latter reflects earned
reputation.

### 6.2 Product catalogue and discovery (M1)
A reviewer submits a product by pasting a Shopee/Lazada URL, stored as `source_url`;
an administrator manually assigns the canonical name (Brand, Line, Key Spec,
Descriptor) to consolidate duplicate listings. Community **price observations**
populate `price_history`; a price panel is shown only when ≥ 3 independent
observations exist. Automated name standardisation is deliberately out of scope
(ToS).

### 6.3 Reviews, versioning, and the publication gate (M1 + M2)
A submitted review is **not public**: it is hidden (`published_at IS NULL`) and
auto-queued (`earn_eligible_status = pending`). Editing a review creates an immutable
snapshot in `review_versions` (full history is retrievable). A moderator resolves
each queued review from a single card:

```
author submits review ──▶ hidden, pending ──▶ MODERATOR QUEUE
   ├─ paste affiliate link (★≥3, verified)  ──▶ monetized + published (atomic)
   ├─ publish without link (★≤2 → honesty_fund; else approved) ──▶ published
   └─ reject (with specific reason)          ──▶ stays hidden; author edit → pending
```

Attaching a link **monetises and publishes in one atomic action**. The response and
all public bodies expose only `referral_redirect_url = /r/{id}` — the raw URL is
never rendered. Product aggregates count published reviews only.

### 6.4 Attribution redirect (M2)
`GET /r/{review_id}` (public, no auth) 302-redirects to the affiliate destination
and records a `sessions` row (destination, platform, click_ref, optional user,
UA/IP with PII deadlines). Because every outbound click passes through this
endpoint, all attribution is captured server-side.

### 6.5 Community voting and Wilson ranking (M2)
Equal-weight up/down votes on published reviews (`review_votes`), one vote per user
(changing a vote is an upsert, not a second vote), no self-voting, rate-limited. Each
vote write recomputes — in a single transaction — the review's counters, its
time-decayed Wilson score, and the author's helpfulness ratio and trust. Listings can
be ranked with `GET /reviews?sort=wilson`; a nightly job re-decays all scored reviews.

### 6.6 Trust progression and badges (M2)
`reputation_score` (0–100) and `trust_stage` (0–5) are recomputed on
publish/unpublish/reject, on vote writes, and by a nightly sweep. Stage badges are
awarded on the way up and never removed. Stages move **only** through recomputation —
there is no endpoint to set a stage directly. The public surface is
`GET /users/{id}/trust`. Formulas are given in §7.

### 6.7 Seller and product trust ratings (M2)
`products.trust_score` is a decayed Wilson score over published reviews rated ≥ 4★;
`users.seller_trust_score` is a decayed Wilson score over seller-review
recommendations, with per-dimension aggregates in JSONB. Config-driven visibility
thresholds (default **off** for cold-start) can hide low-trust products from
listings while keeping them fetchable by id with `low_trust: true`.

> **Withdrawn 2026-07-28 (owner decision).** Seller trust ratings were built and
> verified in M2, then removed: bluntly.ph is an affiliate-review platform, not a
> seller directory. The frontend, API, model and table were removed;
> `0024_drop_seller_reviews` (applied 2026-08-19) drops the data. **Product**
> trust ratings (`products.trust_score`, first paragraph above) are unaffected and
> remain live. Frontend removal: `cf7afbc`; backend removal: `8936dda`;
> types/remnants sweep: `9366a5b`; verification-script update: `b0f8ba0`.

### 6.8 Fraud and collusion signals (M2 — advisory only)
`fraud_service` computes, on read, for the moderator queue card only: **velocity**
(> 10 upvotes/hour), **collusion** (≥ 5 upvoters with > 0.6 author-reciprocated
rate), and **duplicate content** (pg_trgm similarity > 0.85 on same product/author).
These signals are **never public and never auto-block** — they inform a human. This
realises the spec's seven-layer deterrence philosophy without ceding judgment to an
algorithm (§10.2).

### 6.9 Commission reconciliation and the tiered split (M2)
A moderator uploads the monthly affiliate CSV. The importer performs all-or-nothing
validation (422 with per-line issues), matches `sessions` by click_ref/order_ref,
computes the tiered split, credits the reviewer's wallet, and marks sessions
converted — in one transaction, idempotent by `(filename:sha256, line)`. The split
holds the Honesty Fund at a fixed 30 %; the reviewer's share comes from the tier's
`revenue_share_bps`, snapshotted per commission; the platform absorbs rounding so the
three shares re-sum to the gross exactly (verified to the centavo).

### 6.10 Token economy (M2)
An append-only ledger (`token_transactions`) mirrors `users.token_balance` under a
row lock. Earning hooks: first publish (+10) and each reconciled commission (+25),
each idempotent. Admin grant/deduct requires a note. Tokens are spent on the request
board (§6.11).

### 6.11 Request board (M3)
Users escrow tokens to request a review of a product. An **AI validation** step
rejects thin requests (422 `request_invalid` with reasons). Up-votes add a
platform-minted top-up to the effective reward, capped. A reviewer fulfils the
request with their own published review and receives the bounty plus top-up. Open
requests expire after a TTL (escrow refunded). Escrow always resolves exactly once —
refunded XOR paid out (a global invariant, §12).

### 6.12 Revenue-share contracts (M3)
Monetising a review auto-creates a **contract** (`review_contracts`) with a term
(default 6 months) and `auto_renew`. Re-attaching a link reuses the same contract. A
nightly sweep renews or expires contracts. At reconciliation an **expired or
bought-out contract zeroes the reviewer's share** (the Honesty Fund's 30 % still
applies; the platform takes the remainder). A moderator may offer a **buyout**; the
reviewer accepts (wallet credited once) or rejects (no money moves).

### 6.13 Payouts and the PayPal adapter (M3)
Payouts are scheduled by **membership-tier priority** (special → founding →
standard). Users need a valid payout account and a wallet ≥ ₱300. Scheduling reserves
the balance; a payout can be marked paid, failed (wallet refunded), retried, or
cancelled (refunded), each idempotent. A **PayPal Payouts v1 adapter** is built to
the documented contract, but a **manual rail** (`mark-paid`) is always available, so
the entire flow is testable with **no PayPal credentials**. `production_issues()`
refuses a `paypal_live` boot that lacks credentials or still points at the sandbox.

### 6.14 Honesty Fund (M2)
A monthly Celery job (plus an admin trigger) pools the cycle's honesty shares and
distributes them to published ≤ 2★ reviews weighted by the Honesty Score (§7.4).
Payouts are floor-rounded (dust remains in the pool) and the cycle is idempotent —
a re-run aborts.

### 6.15 Affiliate report ingestion (M3)
Ingestion accepts the **real** Shopee and Lazada affiliate exports the owner is
entitled to download — including the Lazada report's cp1252 (not UTF-8) encoding.
Rows that are pending, cancelled, rejected, or zero-value are never payable; payable
rows without a sub-ID are reported as unmatched (nobody is paid without attribution).
Re-importing a file skips all rows as duplicates. See `docs/AFFILIATE_REPORT_FORMATS.md`.

### 6.16 Moderation and audit (M1–M3)
`moderation_logs` doubles as the audit log (DEVIATIONS §4): its action enum is
broadened with audit actions (csv_import, payout, honesty_fund_distribution,
affiliate_link_attach/revoke, publish/unpublish, override). Every administrative
state change is logged with a polymorphic target and JSONB context.

---

## 7. Core Algorithms and Formulas

All incentive math lives in pure, unit-tested functions (`app/services/trust.py`,
`ranking.py`, `earnings.py`). The formulas below resolve ambiguities the source
specification left open (PRD Open Ambiguities A1, A2, A9).

### 7.1 Reputation score — ADR-003
`reputation_score ∈ [0, 100]`, a deterministic blend:

| Component | Formula | Cap |
|---|---|---|
| Helpfulness | `0.60 × helpfulness_ratio` | 60 |
| Verified-review volume | `10 × log₁₀(1 + verified_review_count)` | 25 |
| Best Answers | `3 × best_answer_count` | 15 |
| Strike penalty | `− 15 × strikes` | — |

`score = clamp(helpfulness + volume + best_answers − penalty, 0, 100)`.

### 7.2 Trust stages and gate vote weight — FR-7 / ADR-003
Stage multipliers `{0:0, 1:0.25, 2:1.0, 3:1.5, 4:2.0, 5:3.0}`. `gate_vote_weight` =
multiplier × (reputation_score / 100) for Stage 2+, a flat 0.25 for Stage 1, and 0
for Stage 0 or probation; halved for accounts younger than 30 days. Stage unlock
criteria are encoded in `determine_stage()` (e.g. Stage 2 = first verified review;
Stage 5 = ≥ 50 verified reviews, ≥ 90 % helpfulness, ≥ 6 months active).

### 7.3 Wilson score, decay, and fraud thresholds — ADR-004
| Parameter | Value |
|---|---|
| Confidence z | 1.95996 (two-sided 95 %) |
| Time-decay | exponential, half-life **45 days** |
| Velocity flag | > 10 upvotes / 3600 s sliding window |
| Reciprocity (collusion) flag | reciprocal rate > 0.60 over ≥ 5 shared targets |
| Post-Seeding gate | Wilson lower bound (on *effective n*) ≥ 0.65 **and** ≥ 3 Stage-2+ voters |
| Phase transition | ≥ 50 Stage-2+ verified reviewers in the pilot category |

The Wilson lower bound accepts weighted (non-integer) counts so it runs on
*effective n* (trust-weighted) for the gate and on decayed counts for visibility.

### 7.4 Revenue split and Honesty Score — FR-6 / `constants.py`
Every commission splits **40 % platform / 30 % reviewer / 30 % Honesty Fund**
(centavo-exact). `Honesty Score = trust-weighted helpful votes × price-bracket
multiplier`, where the multiplier is 1.0× (< ₱500), 1.5× (₱500–1,499), or 2.0×
(≥ ₱1,500). A user's monthly Honesty Fund payout is `(their score ÷ total eligible
scores) × pool`.

---

## 8. Background Jobs (Celery beat, Asia/Manila)

| Job | Task | Schedule |
|---|---|---|
| Honesty Fund distribution | `run_honesty_fund_distribution` | Monthly, 1st @ 02:00 |
| PII retention sweep | `run_pii_retention` | Daily @ 03:00 |
| Wilson re-decay | `recompute_wilson_scores` | Daily @ 04:00 |
| Trust re-computation | `recompute_all_trust` | Daily @ 04:30 |
| Contract sweep (renew/expire) | `sweep_contracts` | Daily @ 05:00 |
| Request expiry (escrow refund) | `expire_requests` | Daily @ 05:30 |
| Payout scheduling | `schedule_payouts` | Monthly, 5th @ 02:30 |
| Payout batch refresh | `refresh_payout_batches` | Daily @ 06:00 |

All task bodies are real (not stubs) and share the service layer with the API, so a
job and its equivalent admin-trigger endpoint execute identical code.

---

## 9. API Design and Contract

- **Versioning:** all routes under `/api/v1`.
- **OpenAPI:** the FastAPI-generated document is a **governed artifact**, exported to
  `docs/openapi.json` and consumed by the frontend as `lib/api-types.d.ts`; every
  endpoint is tagged and summarised, verified in sync with the committed spec.
- **Errors:** a single RFC 9457 `problem+json` shape, always carrying a stable
  machine-readable `code` (e.g. `cannot_vote_own_review`, `insufficient_tokens`,
  `request_invalid`), documented for the frontend in `docs/FRONTEND_INTEGRATION.md`.
- **Health:** `GET /health` is DB-free, so it remains a cheap, always-green
  load-balancer probe even under pool saturation.

---

## 10. Security and Privacy

### 10.1 Transport and access
TLS everywhere; RBAC enforced at the API layer off the DB role; RLS on every public
table as defense-in-depth.

### 10.2 Fraud-deterrence framework (seven layers, FR-8)
The backend realises the spec's frictional-deterrence model — physical-photo proof,
fuzzy/plagiarism matching (pg_trgm), reverse-image/metadata review, IP-based
multi-account signals, time-decayed Wilson ranking with velocity flags, community
reporting with 3-report / Stage-4+ escalation, and trust-weighted *effective-n* gate
voting — plus reciprocity-based collusion detection. Crucially, **all layers are
advisory to a human moderator; no path auto-blocks content.**

### 10.3 Privacy (RA 10173)
The `sessions` table operationalises *storage limitation*: IP addresses are replaced
by a salted SHA-256 hash at 30 days and purged at 90; user-agent strings are purged
at 90. The retention sweep is bulk SQL whose hash is proven, in tests, to match the
Python `services/pii.hash_ip` implementation exactly (parity). `PII_HASH_SALT` is a
required non-default value in production. Payout account identifiers are treated as
sensitive personal data.

### 10.4 Production boot guard
`Settings.production_issues()` refuses to start the app in production if any hard
requirement is unmet: a weak `JWT_SECRET`, a localhost/unset database, wildcard CORS,
a default `PII_HASH_SALT`, a `paypal_live` provider lacking credentials, the app
pointed at the session pooler (§11.1), or `THREADPOOL_TOKENS` exceeding the pool
capacity (§11.2).

---

## 11. Performance and Concurrency

### 11.1 The connection-pooler split (a production defect found by testing)
Post-deployment testing against Supabase revealed that the **session pooler admits
only ~4 concurrent clients** (`EMAXCONNSESSION`) — a two-worker + Celery deployment
500s under any real load on it. The fix routes the **application to the transaction
pooler (port 6543)**, which multiplexes 30+ clients, while keeping **Alembic on the
session pooler (port 5432)** because migrations need a real session for
`ALTER TYPE … ADD VALUE`. Prepared statements are disabled for the transaction
pooler (required for pgbouncer transaction mode). The split is locked in by tests and
enforced by the production boot guard.

### 11.2 Connection budget
`Total connections ≈ workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) + Celery` = `2 × 20 +
~4 ≈ 44`. The invariant `THREADPOOL_TOKENS ≤ DB_POOL_SIZE + DB_MAX_OVERFLOW` is
enforced at startup: because every sync endpoint holds its DB session for the whole
request, admitting more concurrent requests than the pool can serve adds no
throughput and would 500 the surplus on pool timeout.

### 11.3 Load test (M3)
Profile: 70 % public reads, 15 % authenticated browse, 10 % review submit, 5 %
moderator queue. Result at **100 users / 5 min / 19,767 requests** (local): aggregate
**p95 73 ms**, error rate **0.0101 %** (two client-side socket aborts, no server
errors), **zero 5xx**. The test also caught — and the team then fixed — a real
defect in which one slow endpoint starved every other via pool exhaustion.

| Target | Result |
|---|---|
| p95 read < 500 ms | ✅ 73 ms aggregate |
| p95 write < 1 s | ✅ 110 ms (`POST /reviews`) |
| error rate < 0.1 % | ✅ 0.0101 % |
| zero 5xx | ✅ none |

**Known hot spot (recorded, not improvised over):** `GET /admin/review-queue`
computes advisory fraud signals per card (~5 queries each), reaching ~9 s for a
25-card page against Supabase. It does not breach the pinned targets (5 % of traffic,
few moderators) and no longer starves other endpoints after the pool fix; a set-based
rewrite is deferred to an explicit owner decision. Immediate mitigation: page with
`?limit=10`.

---

## 12. Testing and Verification

Verification is layered and, critically, **run against both a local PostgreSQL and
the live Supabase project** so that "works on my machine" cannot hide a production
defect. All results below are current as of 2026-07-17.

| Layer | Tool | Result |
|---|---|---|
| Unit + integration | `pytest` | **159 passed**, 0 failed/errored/skipped |
| End-to-end milestone claims | `scripts/verify_milestones.py` | **49/49** (M1 + M2 + M3) |
| Schema truth + whole-DB financial invariants | `scripts/supabase_verify.py` | **59/59** |
| API smoke (incl. concurrency burst) | `scripts/api_smoke.py` | passing, 0 server errors |
| Lint | `ruff` | clean |
| OpenAPI / TS types in sync | `export_openapi` / `gen:api` | no drift |

**What the milestone and schema verifiers actually assert** (a distinguishing
feature of this project's methodology): not merely HTTP 200s, but row-level truth and
whole-database integrity — e.g. *every* `users.token_balance` equals the sum of its
ledger; *every* commission's three shares re-sum to gross exactly; no earn event is
awarded twice anywhere; every request escrow resolves exactly once; passwords are
Argon2id; the raw affiliate URL appears in no public body. The suite also uses
**negative controls** — deliberately breaking an invariant to confirm the check
fails — which previously surfaced two coverage gaps that were then closed.

> **Post-report note (2026-07-28):** every "49/49" figure in this report (Abstract,
> this table, §15, Appendix A) reflects `scripts/verify_milestones.py` as it stood
> at the time of writing (2026-07-17), before the seller trust-ratings withdrawal.
> That check ("M2: Wilson trust rating for SELLERS + dimension averages") was
> removed with the feature (`b0f8ba0`), so the script now totals **48** checks. It
> has been verified by inspection only, **not yet re-executed** against a live
> environment — see `docs/MILESTONES.md` for the corrected, dated figure and
> caveat. This report's historical figures are left as originally recorded.

Coverage maps to the capstone's ISO/IEC 25010:2011 evaluation as follows:
*functional suitability* and *reliability* via the integration and invariant suites;
*performance efficiency* via the load test with pinned targets; *security* via the
auth/RBAC/RLS/PII tests and the seven-layer fraud checks; *maintainability* via lint,
the governed OpenAPI contract, and reversible migrations.

---

## 13. Deviations from the Original Specification

Every divergence is catalogued in `docs/DEVIATIONS.md`; the principal ones:

| Area | Spec | As built | Governing ADR |
|---|---|---|---|
| Identity | Supabase Auth (JWKS), no app password | FastAPI-native JWT + Argon2id; `password_hash` re-added | ADR-010/011 |
| Membership | roles + 6 trust stages | added distinct **membership tiers** (Special/Founding/Standard) | ADR-012 |
| AI | deferred to M5 | provider-abstracted **AI critique** (default stub) | ADR-013 |
| Affiliate platforms | Shopee/Lazada | + **Amazon** in the platform enum | — |
| Earnings | wallet + PayPal | **token economy** + tiered split + tier-priority payouts | — |
| Marketplace data | "Scrapy + proxy rotation" (M3 milestone text) | **no scraping, ever** — manual CSV of first-party reports | MILESTONES §resolution |
| `commissions.review_id` | polymorphic TEXT | typed enum + real FKs with CHECK | DEVIATIONS §3 |
| `reputation_score`, Wilson/decay params | undefined | defined, pinned, unit-tested | ADR-003/004 |
| Seller trust ratings | delivered and verified in M2 (`seller_reviews`, `users.seller_trust_score`) | **withdrawn 2026-07-28** (owner decision): bluntly.ph is an affiliate-review platform, not a seller directory; frontend/API/model removed, table drop `0024_drop_seller_reviews` (applied 2026-08-19) | §6.7; `MILESTONES.md` |

The single most consequential deviation is the **permanent rejection of the
milestone's scraping pipeline**: it directly contradicts the anti-scraping mandate on
which the whole manual-first design rests, and the owner resolved it in favour of
manual, first-party report ingestion.

---

## 14. Limitations and Future Work

### 14.1 Built but not yet deployed (M3 completion, owner-blocked)
- **Production deployment** awaits an owner-supplied host and secrets;
  `docs/PRODUCTION.md` is the runbook and `production_issues()` is the boot gate.
- **Live PayPal sandbox verification** awaits credentials; everything else is
  verified through mocks and the manual rail.
- **Operator prerequisite:** affiliate links must be generated carrying their
  `suggested_sub_id`, or commissions cannot be attributed.
- **No frontend pages exist** — the frontend was always a separate track; the backend
  delivers readiness (OpenAPI, TS types, integration guide).

### 14.2 Known operational limits
- **Single-moderator bottleneck:** the human moderator gates every earning decision,
  canonicalises every product, generates every link, and imports every CSV — a
  launch-state design the spec itself flags as non-scaling.
- **Moderator-queue latency** (§11.3) needs a set-based rewrite before heavy use.

### 14.3 Future milestones (M4/M5)
Evaluation launch and operations (M4); and, gated on cleared external blockers,
Post-Seeding auto-queueing, an NLP fake-review classifier, automated name
standardisation, GCash/Maya payouts (RA 11967 registration), category expansion, and
a formal ISO/IEC 27001 ISMS with WCAG uplift (M5).

---

## 15. Conclusion

The Bluntly.ph backend is a functionally complete, verified implementation of the
capstone's core thesis. It turns the platform's incentive-alignment philosophy into
running, tested code: proof-gated verification, a moderator-mediated publication and
affiliate flow that never leaks the raw link, a defined and testable trust/ranking
mathematics, a centavo-exact revenue engine with an Honesty Fund for honest negative
reviews, and a privacy regime that hashes and purges PII on schedule — all behind a
governed REST contract and proven against the production database with 159 tests,
49/49 milestone claims, and 59/59 integrity checks. The work that remains is
principally *operational and external* (deployment, PayPal credentials, and the
single-moderator scaling question), not a matter of unfinished core logic. The system
is, by its own automated evidence, ready for the evaluation phase once deployed.

---

## Appendix A — Verification commands (reproducible)

Run from `backend/` with the project virtualenv; prefix with `USE_SUPABASE=true` to
target the live Supabase project instead of local PostgreSQL:

```bash
python -m pytest                       # 159 unit/integration tests
python -m scripts.verify_milestones    # 49/49 end-to-end M1–M3 claims
python -m scripts.supabase_verify      # 59/59 schema + financial invariants
python -m scripts.api_smoke --base-url <url> --concurrency
python -m ruff check app scripts tests
```

## Appendix B — Source documents

`docs/01-bluntly-ph-PRD.md` · `docs/02-bluntly-ph-architecture.md` ·
`docs/03-bluntly-ph-roadmap.md` · `docs/MILESTONES.md` · `docs/DEVIATIONS.md` ·
`docs/schema.md` · `docs/ARCHITECTURE_AS_BUILT.md` · `docs/PRODUCTION.md` ·
`docs/AFFILIATE_REPORT_FORMATS.md` · `docs/LOADTEST_RESULTS.md` ·
`docs/FRONTEND_INTEGRATION.md` · `docs/adr/001–013` ·
`docs/M1_TEST_PLAN.md` · `docs/M2_TEST_PLAN.md` · `docs/M3_TEST_PLAN.md`.
