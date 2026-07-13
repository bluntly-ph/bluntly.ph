# Bluntly.ph Backend — As-Built Architecture (M0 + M1 + M2 slice 1)

> The definitive "how it actually works" reference, written from **verified**
> behavior (51/51 API checks + 62 unit/integration tests, green on local **and**
> Supabase, 2026-07-13). Supersedes intentions in `02-bluntly-ph-architecture.md`
> where they differ. Planning is done on Fable 5; implementation/testing on Opus 4.8.

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
| ORM / migrations | SQLAlchemy 2.0 + Alembic (5 migrations) |
| Database | PostgreSQL 16 local (docker-compose) / **Supabase** PostgreSQL 17 (session pooler, IPv4) |
| Cache / broker | Redis 7 |
| Background jobs | Celery worker + beat (Honesty Fund monthly, PII retention daily — stubs pending M2) |
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
                    │     threadpool (40 tokens)    │
                    │   • JWT auth, RBAC, RFC 9457  │
                    └───┬───────────┬───────────┬───┘
              SQLAlchemy│   Redis   │           │ https
              pool(5+5) │  (limiter,│           │ (only if AI_PROVIDER=claude/openai)
                        ▼   broker) ▼           ▼
             ┌───────────────┐ ┌────────┐  ┌──────────────┐
             │ PostgreSQL    │ │ Redis 7│  │ Anthropic /  │
             │ local OR      │ └───┬────┘  │ OpenAI API   │
             │ Supabase      │     │broker └──────────────┘
             │ (RLS, 19 tbls)│     ▼
             └───────────────┘  Celery worker + beat
```

Supabase is a **separate managed service** (its own cloud, ap-southeast). The app
reaches it via the **session-pooler** connection string (IPv4; the direct
`db.<ref>.supabase.co` host is IPv6-only and unreachable from IPv4 networks).

## 4. Request lifecycle

1. TLS terminator → Uvicorn worker → FastAPI.
2. Sync `def` endpoint runs in the **AnyIO threadpool** (ceiling `THREADPOOL_TOKENS`,
   default 40) — the in-flight concurrency cap per process.
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

## 6. Data model (19 tables, `public` schema, all RLS-enabled)

Core: `users` (profile + `role`/`membership_tier`/`reputation`/`wallet`), `badges`,
`user_badges`, `products`, `product_platforms` (`is_monetizable`), `price_history`,
`reviews`, `review_versions`, **`referral_links`**, `questions`, `answers`,
`seller_reviews`, `sessions` (affiliate clicks + PII lifecycle), `commissions`,
`honesty_fund_distributions`, `moderation_logs` (also the audit log),
`earn_eligible_votes`, `membership_tiers`, + `alembic_version` (RLS on). Full
column reference: `docs/schema.md`.

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

## 9. Concurrency model & connection budget

- Sync endpoints run in the AnyIO threadpool → per-process in-flight cap =
  `THREADPOOL_TOKENS` (40).
- Each process holds a DB pool of `DB_POOL_SIZE`+`DB_MAX_OVERFLOW` (5+5), 10s
  fail-fast timeout, 300s recycle (pooler-safe).
- **Total DB connections ≈ `workers × (pool_size + overflow) + Celery`.** Defaults:
  `2 × 10 + ~4 ≈ 24` — sized to fit the Supabase session pooler. Scale workers and
  pool together; keep the product under the pooler max.
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
| Unit + integration tests (`pytest`) | 62 passed |
| Lint (`ruff`) | clean |
| Migrations (up / down / up, clean slate) | reversible, 5 migrations |
| API smoke — **local** (`scripts/api_smoke.py`, 51 checks) | 51/51 |
| API smoke — **Supabase** (:8001, same 51 checks) | 51/51 |
| Concurrency burst (80 req) — local & Supabase | 0 server errors |
| Supabase RLS advisor | clean (no public table without RLS) |

Reusable tool: `python -m scripts.api_smoke --base-url <url> [--concurrency]`
(promotes a moderator directly via the DB, so it works against local or Supabase).

## 12. Milestone status & what's next

- **Done:** M0 foundations · M1 core (auth, tiers, reviews+versions, AI critique) ·
  **M2 slice 1** (publication-gated referral link flow) · production hardening ·
  performance P0 (pool tuning, N+1 fix, 2 workers, threadpool knob).
- **Next M2 slices:** Wilson trust ratings, fake/shill + collusion detection, trust
  thresholds, upvote/downvote, tier-based revenue split, token economy + CSV
  reconciliation.
- **M3 flag:** the milestone's Scrapy pipeline contradicts the anti-scraping mandate
  — needs an explicit decision before build (`docs/MILESTONES.md`).
