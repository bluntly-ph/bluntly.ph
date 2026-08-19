# Bluntly.ph Backend — As-Built Architecture (M0 + M1 + M2 complete, M3 built-not-deployed)

> The definitive "how it actually works" reference, written from **verified**
> behavior (78/78 API smoke checks + 141 unit/integration tests + 59/59 deep
> verification, green on local **and** Supabase, 2026-07-16). Supersedes intentions in
> `02-bluntly-ph-architecture.md` where they differ.

---

## 1. What it is

A FastAPI backend for a verified product-review platform: accounts, membership
tiers, structured reviews with version history, AI critique, and a **moderator-
manual referral (affiliate) link flow** with a publication gate. Every marketplace
touchpoint is admin-mediated — **no scraping, no marketplace API calls**.

## 2. Tech stack (as built)

| Layer | Choice |
|---|---|
| API | FastAPI (sync endpoints), Uvicorn (2 workers, no `--reload` in ship path) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic (14 migrations, head `0013_referral_sub_id`) |
| Database | PostgreSQL 16 local (docker-compose) / **Supabase** PostgreSQL 17 (session pooler, IPv4) |
| Cache / broker | Redis 7 |
| Background jobs | Celery worker + beat (Honesty Fund monthly 02:00 · PII retention daily 03:00 · Wilson/trust-rating recompute daily 04:00 · trust-progression sweep daily 04:30, Asia/Manila) — real bodies as of M2 |
| Auth | FastAPI-native **JWT/OAuth2**, **Argon2id** password hashing (ADR-010/011) |
| AI critique | Provider-abstracted (stub default / Claude / OpenAI; ADR-013) |
| Error contract | **RFC 9457** `application/problem+json`, everywhere |
| Config | pydantic-settings, 12-factor, `.env` shared with the Next.js frontend |

## 3. Topology

```
                         HTTPS
   Clients ───────────────▶ TLS terminator / load balancer
   (browser, mobile)              │        (health probe: GET /health — DB-free)
                                  ▼
                    ┌──────────────────────────────┐
                    │  Uvicorn (2 workers/container)│
                    │  FastAPI app                  │
                    │   • sync endpoints → AnyIO    │
                    │     threadpool (20 tokens)    │
                    │   • JWT auth, RBAC, RFC 9457  │
                    └───┬───────────┬───────────┬───┘
              SQLAlchemy│   Redis   │           │ https
            pool(10+10) │  (limiter,│           │ (only if AI_PROVIDER=claude/openai)
                        ▼   broker) ▼           ▼
             ┌───────────────┐ ┌────────┐  ┌──────────────┐
             │ PostgreSQL    │ │ Redis 7│  │ Anthropic /  │
             │ local OR      │ └───┬────┘  │ OpenAI API   │
             │ Supabase      │     │broker └──────────────┘
             │ (RLS, 25 tbls)│     ▼
             └───────────────┘  Celery worker + beat
```

Supabase is a **separate managed service** (its own cloud, ap-southeast). Two
connection paths, deliberately:

* **App → TRANSACTION pooler (:6543).** Measured 2026-07-16: the session pooler
  accepts only **4** concurrent clients (`EMAXCONNSESSION`) — a 2-worker + Celery
  deployment 500s under load on it. Transaction mode multiplexes many clients
  onto few server connections and accepted 30+. `production_issues()` refuses to
  boot if the app is pointed anywhere else.
* **Alembic → SESSION pooler (:5432).** Migrations run `ALTER TYPE ... ADD VALUE`
  in `autocommit_block()`, which needs a real session.

Both are IPv4; the direct `db.<ref>.supabase.co` host is IPv6-only and
unreachable from IPv4 networks.

## 4. Request lifecycle

1. TLS terminator → Uvicorn worker → FastAPI.
2. Sync `def` endpoint runs in the **AnyIO threadpool** (ceiling `THREADPOOL_TOKENS`,
   default 20) — the in-flight concurrency cap per process. It must stay **<=
   `DB_POOL_SIZE + DB_MAX_OVERFLOW`** (enforced by `production_issues()`): every
   sync endpoint holds its session for the whole request, so admitting more adds
   no throughput and makes the surplus 500 on pool timeout (proved by the M3
   load test — see `docs/LOADTEST_RESULTS.md`).
3. `get_db` yields a SQLAlchemy `Session` from a pool
   (`DB_POOL_SIZE`+`DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT=10s` fail-fast).
4. Auth deps: `get_current_user` validates the HS256 JWT and loads the `User`;
   **RBAC reads `users.role` from the DB**, never trusts the token claim.
5. Handler → service → ORM; response serialized by a Pydantic schema.
6. Any error → a registered handler emits RFC 9457 `problem+json`
   (`type,title,status,detail,instance,code[,extra]`).

## 5. Auth & RBAC (ADR-010/011)

- `POST /auth/register` (Argon2id hash) · `POST /auth/login` (OAuth2 password form,
  `username`=email) · `GET /auth/me`.
- HS256 JWT (`JWT_SECRET`, `iss=bluntly-ph`, `sub`, `role`, `exp`).
- `require_role("moderator")` gates admin routes off the **DB role** — so promoting
  a user to moderator takes effect immediately, without re-login (verified).
- Auth endpoints are Redis rate-limited (fail-open; default 10/min/IP).

## 6. Data model (25 tables, `public` schema, all RLS-enabled)

Core: `users` (profile + `role`/`membership_tier`/`reputation`/`wallet`/
`token_balance`/`seller_trust_score` — **seller_trust_score withdrawn 2026-07-28,
see §8b note**), `badges`, `user_badges`, `products`
(+ `trust_score`), `product_platforms` (`is_monetizable`), `price_history`,
`reviews`, `review_versions`, **`referral_links`**, **`review_votes`** (equal-weight
community votes, M2 s2), `questions`, `answers`, `seller_reviews`
(one per seller+reviewer — **withdrawn 2026-07-28**, `0024_drop_seller_reviews`
written not yet applied), `sessions` (affiliate clicks + PII lifecycle),
`commissions` (+ tier snapshot columns), `honesty_fund_distributions`,
`moderation_logs` (also the audit log), `earn_eligible_votes`,
**`token_transactions`** (append-only ledger, M2 s7), `membership_tiers`,
**`review_requests`** + **`request_upvotes`** (request board, M3 s9),
**`review_contracts`** (revenue-share contracts, M3 s10), **`payouts`**
(disbursement; RLS with no public policy, M3 s11),
+ `alembic_version` (RLS on). Extension `pg_trgm` powers the duplicate-content
signal. Full column reference: `docs/schema.md`.

RLS is defense-in-depth: the backend connects as the DB owner and enforces RBAC in
the API layer, so RLS constrains any *direct* Supabase (PostgREST) access. Every
`public` table has RLS enabled (Supabase advisor: clean).

## 7. The publication gate + referral state machine (M2 slice 1) — the heart of it

**A new review is NOT public.** It is hidden (`reviews.published_at IS NULL`) and
auto-queued (`earn_eligible_status = pending`). A moderator publishes it — pasting a
referral link both **monetizes and publishes** in one atomic action.

```
 author submits review ──▶ published_at=NULL (hidden), status=pending ──▶ MODERATOR QUEUE
                                                                                │
   GET /api/v1/admin/review-queue  (one card: review + stars + author +        │
     product.source_url + suggested_platform)                                  │
                                                                               │
      ┌──────────────── paste link (★≥3, verified) ───────────────────────────┤
      ▼                                                                        │
  POST /admin/reviews/{id}/referral-link  {url, platform}                      │
   validate URL (https, allowlisted domain per platform, monetizable)          │
   → referral_links(active) + reviews.affiliate_link mirror                    │
   → status=monetized, published_at=now()   ── LIVE, with link ──┐             │
                                                                 │             │
      ┌─────────── publish w/o link ──────────┐   ┌── reject (reason) ────────┤
      ▼ POST /publish                          │   ▼ POST /reject              │
  ★≤2 → honesty_fund ; else → approved         │  status=rejected, stays hidden;
  published_at=now()  ── LIVE, no link ────────┘  author edit → back to pending
                                                                 │
   DELETE /referral-link {reason}  → link revoked, affiliate_link cleared,
     status=approved, STAYS published (link pending again)  ◀────┘
   POST /unpublish  → published_at=NULL (off the site), independent of link state
```

Invariants (all verified): one `active` link per review (partial unique index);
`★≤2`/non-monetizable can't be link-monetized (409); **unverified reviews can't be
monetized** (409, guard beyond spec, per FR-3); editing a monetized review flags it
`edited_since_monetized` in the queue (compares `current_version` to the link's
snapshot); product aggregates count **published** reviews only.

## 8. Attribution redirect (public, no auth)

```
 GET /r/{review_id}
   review published + monetized + active link ?  ── no ──▶ 404 problem+json
        │ yes
        ▼  record_click: sessions row (destination_url, platform, click_ref,
           user_id if token, UA + IP with PII deadlines via services/pii;
           invalid IPs stored NULL) ──▶ 302 → affiliate URL
```

The **raw affiliate URL is never exposed** in any API body — `ReviewOut` carries
only `referral_redirect_url = /r/{id}` (present once published+monetized). So every
outbound click is attributed.

## 8b. Reputation, trust & earnings systems (M2 slices 2–8)

- **Community voting** (`review_votes`): equal-weight up/down on published reviews,
  one vote per user (upsert to change), no self-votes, rate-limited
  (`VOTE_RATE_LIMIT_MAX`/60s). Every vote write recomputes — in ONE transaction —
  the review's counters + time-decayed Wilson score (45d half-life, ADR-004), the
  author's helpfulness ratio, and the author's trust. `GET /reviews?sort=wilson`
  ranks listings; a nightly 04:00 task re-decays all scored reviews.
- **Trust progression** (`trust_service`): `reputation_score` (ADR-003 blend) and
  `trust_stage` (0–5) recomputed on publish/unpublish/reject, vote writes, and a
  nightly 04:30 sweep over 90-day-active users. Stage badges awarded on the way up,
  never removed. Stages move **only** via recompute — no manual stage endpoint.
  Public surface: `GET /users/{id}/trust`.
- **Product & seller trust ratings**: `products.trust_score` = decayed Wilson over
  published reviews' stars ≥ 4 (updated with product aggregates on
  publish/unpublish/edit); `users.seller_trust_score` = decayed Wilson over
  seller-review `would_recommend` + per-dimension aggregates in JSONB. Visibility
  thresholds are env-config, default OFF; a filtered product stays fetchable by id
  with `low_trust: true`; seller profiles are flagged, never hidden.
  > **Withdrawn 2026-07-28 (owner decision).** Seller trust ratings were built and
  > verified in M2, then removed: bluntly.ph is an affiliate-review platform, not a
  > seller directory. The frontend, API, model and table were removed;
  > `0024_drop_seller_reviews` (applied 2026-08-19) drops the data. Product
  > trust ratings (`products.trust_score`, above) are unaffected. Frontend removal:
  > `cf7afbc`; backend removal: `8936dda`; types/remnants sweep: `9366a5b`;
  > verification-script update: `b0f8ba0`.
- **Fraud signals** (`fraud_service`, ADVISORY ONLY — FR-8): velocity (>10
  up-votes/h), collusion (≥5 up-voters, >0.6 reciprocated by the author),
  pg_trgm duplicate content (>0.85, same product/author). Computed on read for the
  moderator queue card only; never public; **no auto-block path exists**.
- **Commission reconciliation** (`commission_service`): moderator uploads the
  monthly CSV → all-or-nothing validation (422 with per-line issues) → match
  sessions by `click_ref`/`order_ref` (unmatched rows reported, skipped) →
  `split_commission_tiered` (Honesty Fund fixed 30%; reviewer share from
  `membership_tiers.revenue_share_bps`, snapshotted per commission; platform
  absorbs rounding) → wallet credit + session→converted, one transaction.
  Idempotent by `(filename:sha256, line)`.
- **Token economy** (`token_service`): append-only `token_transactions` ledger with
  `balance_after` chain and row-locked mirror `users.token_balance`. Earning hooks:
  first publish (+10) and each reconciled commission (+25), idempotent via a
  partial unique index. Admin grant/deduct with mandatory note. Spending is M3.
- **Honesty Fund** (`honesty_fund_service`, monthly beat + admin trigger): pool =
  Σ cycle honesty shares; eligible = published ≤2★ reviews; score = gate-weighted
  helpful votes × price bracket; payouts floor-rounded, dust stays; idempotent per
  cycle (re-runs abort).
- **PII retention** (`retention_service`, daily beat): bulk SQL — IP → salted
  SHA-256 at 30d (same hash as `services/pii.hash_ip`, salt `PII_HASH_SALT`
  required in prod), IP-hash + UA purge at 90d.

## 9. Concurrency model & connection budget

- Sync endpoints run in the AnyIO threadpool → per-process in-flight cap =
  `THREADPOOL_TOKENS` (20).
- Each process holds a DB pool of `DB_POOL_SIZE`+`DB_MAX_OVERFLOW` (10+10), 10s
  fail-fast timeout, 300s recycle (pooler-safe).
- **Total DB connections ≈ `workers × (pool_size + overflow) + Celery`.** Defaults:
  `2 × 20 + ~4 ≈ 44` — raised in M3 s14 after the load test showed 5+5 starved
  under 100 users. This is only viable because the app talks to the **transaction
  pooler**, which multiplexes; the session pooler would reject it at 4 clients.
  Scale workers and pool together, and keep
  `THREADPOOL_TOKENS <= pool_size + max_overflow` (enforced at startup).
- The moderator queue is **batch-loaded** (products via one `IN` +
  `selectinload(platforms)`, authors via one `IN`) — no N+1.
- **Verified:** an 80-request burst (30 list + 30 health + 10 queue + 10 submits at
  concurrency 20) returned **zero 5xx/timeouts** on both local and Supabase.

## 10. Deployment topology

- **Local dev:** `backend/docker-compose.yml` — postgres, redis, api (runs
  migrations then serves), worker, beat. First-boot DB/DNS race self-heals
  (`wait_for_db` + `restart: on-failure`).
- **Production:** `APP_ENV=production` (startup guard rejects weak `JWT_SECRET`,
  localhost DB, or wildcard CORS), `USE_SUPABASE=true` +
  `SUPABASE_CONNECTION_STRING_SESSION_POOLER`, `ENABLE_DOCS=false`, managed Redis.
  Run `alembic upgrade head` once as a release step. Full runbook: `docs/PRODUCTION.md`.
- Schema + seed are **live in Supabase** (project `byobedbhodhvocgrkrse`, 19 tables,
  RLS clean).

## 11. Verification summary (ship gate — all green)

| Check | Result |
|---|---|
| Unit + integration tests (`pytest`) | **141 passed** on local AND Supabase |
| Negative controls (invariant deliberately broken → the check must fail) | 15/15 controls behaved; found 2 coverage gaps, now closed |
| Lint (`ruff`) | clean |
| Migrations | 14 total (0001–0013); applied to local AND Supabase |
| API smoke — **local** (`scripts/api_smoke.py`, 78 checks) | 78/78 |
| API smoke — **Supabase** (:8001) | passing |
| Concurrency burst (80 req) — local & Supabase | 0 server errors |
| Deep verification (`scripts/supabase_verify.py`, **59 checks**: schema truth + whole-DB financial integrity invariants + end-to-end flow asserted row-by-row with direct SQL) | **59/59 on local AND Supabase** |
| RLS | every new table RLS-enabled (`review_votes` public-select; `token_transactions` no permissive policy) |

Reusable tool: `python -m scripts.api_smoke --base-url <url> [--concurrency]`
(promotes a moderator directly via the DB, so it works against local or Supabase).

## 12. Milestone status & what's next

- **Load test (M3 s14):** 100 users / 5 min — p95 **73 ms**, errors **0.0101%**,
  **zero 5xx**. See `docs/LOADTEST_RESULTS.md`; it caught a real defect (one slow
  endpoint 500-ing every other via pool starvation) now fixed and guarded.
- **Done:** M0 foundations · M1 core (auth, tiers, reviews+versions, AI critique) ·
  **M2 complete** (publication-gated referral flow · community voting + Wilson
  ranking · trust progression + badges · seller/product trust ratings +
  thresholds (**seller half withdrawn 2026-07-28 — §8b**) · advisory fraud
  signals · commission CSV + tiered split · token economy · Honesty Fund + PII
  retention job bodies) · production hardening · performance P0 (pool tuning,
  N+1 fix, 2 workers, threadpool knob).
- **M3 built, NOT deployed:** request board (slice 9) · contracts (10) · payouts
  + PayPal adapter and manual rail (11) · real Shopee/Lazada report ingestion (12)
  · frontend readiness (13) · load test + acceptance plan (14). Schema 21 → 25
  tables (`review_requests`, `request_upvotes`, `review_contracts`, `payouts`).
- **Remaining for M3 completion (owner-blocked):** production deploy (host +
  secrets) and live PayPal sandbox verification (credentials). Operator
  prerequisite: affiliate links must carry `suggested_sub_id` or commissions
  cannot be attributed — see `docs/AFFILIATE_REPORT_FORMATS.md`.
- **M3 flag:** the milestone's Scrapy pipeline contradicts the anti-scraping mandate
  — needs an explicit decision before build (`docs/MILESTONES.md`).
