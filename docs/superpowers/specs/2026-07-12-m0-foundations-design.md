# M0 Foundations — Design (Bluntly.ph backend)

**Date:** 2026-07-12 · **Status:** Approved & implemented · **Scope:** Sub-project A
(M0). M1 (Core Contribution Loop) and M2 (Incentive Engine & Moderation) are
separate later cycles.

## Context & decisions
- **Stack:** FastAPI (Python 3.12) + SQLAlchemy 2.0 + Alembic + Celery + Redis;
  Postgres/Auth/Storage via Supabase. The global Pieza `CLAUDE.md` Fastify/Prisma +
  GSD mandate was **explicitly set aside for this repo** (user decision) — the
  Bluntly.ph source docs specify Python/FastAPI.
- **Decomposition:** the prompt's "M0+M1+M2" is ~10 build phases; decomposed into
  A/B/C and built A first.
- **Identity:** Supabase Auth owns identity (ADR-001); Redis = app data only.
- **Infra:** docker-compose local Postgres 16 + Redis 7; the same Alembic
  migrations apply to Supabase for staging.

## What M0 delivers
1. **15-table schema** (`app/models/`) + Alembic migrations, incl. UUID PKs +
   human-readable IDs, generated `trust_level_name`, explicit FK CASCADE/SET NULL,
   and **RLS** (`0002_rls_policies.py`, `auth.uid()` parity shim).
2. **Supabase-JWT auth + RBAC scaffold**, language enum.
3. **Governed OpenAPI** (`/docs`, exported to `docs/openapi.json`) with a single
   **RFC 9457** error schema.
4. **Pinned parameters as ADRs** (`docs/adr/001–009`): reputation_score, Wilson
   z/45-day half-life/velocity/reciprocity, tier/member enums, answer-earning out,
   on-platform reverse-image+plagiarism, Supabase-delegated KDF, rate limiting.
5. **Pure, unit-tested services**: trust, ranking, earnings split, PII retention.
6. **Celery** app + beat schedule (Honesty Fund monthly, PII daily) with M2 stubs.
7. **docker-compose, seed script, `.env.example`, README**, and the docs pass:
   `schema.md`, `DEVIATIONS.md`, `MARKETPLACE_INTEGRATION.md`.

## Boundaries drawn for later milestones
- `MarketplaceIntegrationService` interface (M1) isolates all Shopee/Lazada-touching
  logic so manual admin steps are swappable for a future API without reworking
  review/earning/reconciliation. **No scraping / unofficial API anywhere.**
- Post-Seeding gate + phase-transition logic is built as pure functions now
  (`ranking.py`), activated in M2, dormant until 50 Stage-2+ reviewers.

## Verification (all green)
`alembic upgrade/downgrade/upgrade` clean; 41 tests pass (incl. DB integration);
ruff clean; live `/health`, problem+json 401, and `/docs` confirmed by curl.

## Not built now (M5 / out of scope)
NLP name standardization, AI pre-screening, GCash/Maya, multi-moderator tooling,
any Shopee/Lazada API partnership work.
