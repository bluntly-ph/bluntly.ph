# Performance Tuning + Ship-Readiness Verification Plan

**Date:** 2026-07-13 · **Planned on:** Fable 5 · **Implemented/tested on:** Opus 4.8
subagents (model policy). Goal: make the M0–M2s1 backend handle concurrent load
sanely on its actual stack (FastAPI sync endpoints + SQLAlchemy + Supabase session
pooler), then verify end-to-end — local AND Supabase — before calling it shippable.

## A. Bottleneck analysis (as-built facts)

| # | Fact | Consequence under concurrency |
|---|---|---|
| 1 | All endpoints are sync `def` → run in Starlette's AnyIO threadpool, default **40 tokens/process** | Hard in-flight ceiling of 40 req/process; excess queues |
| 2 | `create_engine` uses default pool: **pool_size=5, max_overflow=10, pool_timeout=30s** | 40 threads compete for ≤15 connections → stalls up to 30s, then `TimeoutError` 500s |
| 3 | Supabase **session pooler**: each client connection pins a pooled backend for its lifetime; budget is small and shared by api + Celery worker + beat + ad-hoc scripts | Oversized pools exhaust the pooler → connect errors for everyone |
| 4 | compose api runs `uvicorn --reload`, 1 process | Dev-mode in ship path; no multi-worker scaling |
| 5 | `GET /admin/review-queue` calls `_queue_item` per review → ~4 queries each (product, platforms, author, suggested_platform) | 50 cards ≈ 200 queries/request |
| 6 | Argon2id ≈ 100ms CPU per hash (by design) | Auth bursts eat threadpool + CPU; already rate-limited (10/min/IP) — tests must reuse tokens, not register in loops |
| 7 | `/health` is DB-free | Good — stays the LB probe |

## B. Optimizations to implement (P0 — small, targeted diffs; no gold-plating)

1. **Env-tunable engine pool** (`app/core/config.py` + `app/db/session.py`):
   `DB_POOL_SIZE` (default 5), `DB_MAX_OVERFLOW` (default 5), `DB_POOL_TIMEOUT`
   (default 10s — fail fast instead of 30s pile-ups), `DB_POOL_RECYCLE` (default
   300s — safe for the pooler). Pass into `create_engine`.
2. **Kill the N+1 in the review queue** (`admin_referral.py` + `referral_service.py`):
   batch-load products with `selectinload(Product.platforms)` and authors via one
   `IN` query; compute `suggested_platform` from the preloaded platforms/product
   (no per-item queries). Clamp `limit` to ≤100.
3. **Production server command** (`docker-compose.yml`): drop `--reload`; run
   `uvicorn --workers 2`. Document the **connection budget**: total ≈ workers ×
   (pool_size+overflow) + Celery worker/beat — with the defaults: 2×10 + ~4 ≈ 24,
   sized to fit the Supabase session pooler. Note in PRODUCTION.md.
4. **Threadpool knob** (`app/main.py` startup, optional but cheap):
   `THREADPOOL_TOKENS` env (default 40) via
   `anyio.to_thread.current_default_thread_limiter().total_tokens`. Keeps the
   thread ceiling explicit and tunable alongside the pool.
5. `.env.example` + `docs/PRODUCTION.md`: document all new knobs + budget table.
6. Full test suite + ruff must stay green; rebuild compose.

Explicitly NOT now (M3 scope): async rewrite, caching layer, real load testing,
horizontal autoscaling.

## C. Verification (Opus 4.8 subagents, parallel where safe)

Fixtures are created **once** by the orchestrator (author + moderator tokens per
environment) and handed to agents — no registration loops (rate limit + Argon2).

| Agent | Target | Scope (curl only, bounded) |
|---|---|---|
| **T1 functional** | local :8000 | Full API walkthrough per `backend/API_TESTING.md`: auth /me, tiers + RBAC negatives, products, review CRUD + versions + gate visibility, AI critique (stub), full referral flow (queue → attach → 302 redirect → revoke → re-attach → publish-w/o-link ≤2★ → reject → unpublish), error-contract checks (401/403/404/409/422 problem+json). ≤ ~50 requests. |
| **T2 concurrency smoke** | local :8000 | Bursts with bounded parallelism: 30× parallel `GET /reviews` + `GET /health`, 10× parallel authed review submissions, 10× parallel queue reads. Report status-code histogram + wall time; **PASS = zero 5xx/timeouts**. Not a load test. |
| **T3 Supabase** | :8001 (`USE_SUPABASE=true`, host venv uvicorn) | Condensed functional suite incl. referral flow + redirect + a 10× parallel mini-burst — proves pooler settings hold. Verify click `sessions` row lands in Supabase. |

Each agent writes a report (`scratchpad/report-T*.md`). Orchestrator synthesizes.

## D. Ship gate (all must hold)

- [ ] P0 optimizations merged; 62+ tests pass; ruff clean; migration state unchanged
- [ ] T1 all-pass locally on the rebuilt stack (workers=2, no reload)
- [ ] T2 zero 5xx/timeouts at the smoke levels above
- [ ] T3 all-pass against Supabase (pooler stable under the mini-burst)
- [ ] `docs/ARCHITECTURE_AS_BUILT.md` written from verified behavior (components,
      request lifecycle, publication-gate + referral state machine, attribution
      path, concurrency model + connection budget, deployment topology)
- [ ] DEVIATIONS/PRODUCTION docs updated

## E. Out of scope

Frontend, remaining M2 slices (Wilson/fraud/token economy), M3 load/security
suites, GCash/Maya, scraping decision.
