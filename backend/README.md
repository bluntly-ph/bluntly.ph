# Bluntly.ph Backend (FastAPI)

Verified product & seller review platform. FastAPI + SQLAlchemy 2.0 + Alembic +
Celery + Redis, with PostgreSQL/Storage via Supabase. **M0 Foundations + M1 Core
System** are complete. Identity is a FastAPI-issued JWT (ADR-010).

> Milestones: **M0** foundations + **M1** core system (auth, reviews + version
> history, membership tiers, AI critique) are done. See `../docs/MILESTONES.md`,
> `../docs/DEVIATIONS.md`, and `../docs/adr/`.

## What's here
- **17-table** schema (`app/models/`) + Alembic migrations (`alembic/versions/`)
  incl. RLS policies.
- **FastAPI-native JWT/OAuth2 auth** — Argon2id + HS256 (`app/core/security.py`,
  `app/services/auth_service.py`, `app/api/v1/routes/auth.py`; ADR-010/011).
- **Membership tiers** (Special/Founding/Standard) — config table + assignment
  (`app/api/v1/routes/membership.py`; ADR-012).
- **Reviews + version history** — submission, edit-creates-a-version, version
  archive (`app/services/review_service.py`, `app/api/v1/routes/reviews.py`).
- **AI critique** — provider abstraction (stub/Claude/OpenAI), default stub
  (`app/services/ai_critique.py`; ADR-013).
- RFC 9457 problem+json error contract; governed OpenAPI at `/docs`, exported to
  `../docs/openapi.json`.
- Pure, unit-tested trust & ranking math (`app/services/trust.py`, `ranking.py`).
- Celery app + beat schedule with M2 task stubs; synchronous Redis rate limiting.

## Key endpoints (v1)
`POST /auth/register` · `POST /auth/login` · `GET /auth/me` ·
`POST|GET /products` · `GET /products/{id}` ·
`POST|GET /reviews` · `GET|PATCH /reviews/{id}` · `GET /reviews/{id}/versions[/{n}]` ·
`POST /reviews/{id}/critique` · `POST /ai/critique` ·
`GET /membership-tiers[/{code}]` · `PATCH /membership-tiers/{code}` (mod) ·
`PATCH /users/{id}/membership-tier` (mod).

## Prerequisites
- Docker (for Postgres 16 + Redis 7), **or** local Postgres/Redis.
- Python 3.12 (for running outside Docker).
- A repo-root `.env` (see `.env.example`). Required keys: `DATABASE_URL`,
  `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`,
  `SUPABASE_JWKS_URL`.

## Run with docker-compose (recommended)
```bash
cd backend
docker compose up --build          # postgres, redis, api (runs migrations), worker, beat
# API:   http://localhost:8000/docs
# Health http://localhost:8000/health
```
> **Port conflict warning:** don't run the compose stack *and* the standalone
> `docker run` Postgres/Redis from the "Run locally" section at the same time —
> they both bind `5432` / `6379`, which prevents compose's own Postgres/Redis from
> starting. Use one or the other. Stop stray containers with
> `docker rm -f bluntly_pg bluntly_redis` before `docker compose up`.
> The `api` service waits for the DB (`scripts/wait_for_db.py`) and has
> `restart: on-failure`, so a first-boot DB/DNS race self-heals.

## Run locally (venv)
```bash
cd backend
python -m venv .venv && ./.venv/Scripts/pip install -r requirements-dev.txt   # (Linux/macOS: .venv/bin/pip)

# Start infra only:
docker run -d --name bluntly_pg -e POSTGRES_USER=bluntly -e POSTGRES_PASSWORD=bluntly \
  -e POSTGRES_DB=bluntly -p 5432:5432 postgres:16
docker run -d --name bluntly_redis -p 6379:6379 redis:7

export DATABASE_URL=postgresql+psycopg://bluntly:bluntly@localhost:5432/bluntly
export REDIS_URL=redis://localhost:6379/0

alembic upgrade head            # apply migrations
python -m scripts.seed          # seed badges, moderator, sample products
python -m scripts.export_openapi  # write ../docs/openapi.json
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

## Migrations
```bash
alembic upgrade head            # apply
alembic downgrade base          # revert all (fully reversible)
alembic revision --autogenerate -m "message"   # after model changes
```

## Tests
```bash
pytest                          # full suite (DB tests auto-skip if no Postgres)
SKIP_DB_TESTS=1 pytest          # pure-logic + API tests only
```
Covers (spec §3.4.1 required targets): Wilson computation, phase-transition at 50
reviewers, vote-weight snapshot immutability, commission split arithmetic +
idempotency, PII retention correctness, and the `/health` + error contract.

## Celery
```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info
celery -A app.workers.celery_app.celery_app beat  --loglevel=info
```
Scheduled: monthly Honesty Fund distribution, daily PII retention sweep (stubs in M0).

## Layout
```
app/core/      settings, security(JWT), errors(RFC9457), rate_limit, logging, supabase_client, constants
app/db/        engine/session, declarative base
app/models/    15 ORM models + enums
app/services/  trust, ranking, earnings, pii  (pure, tested)
app/api/v1/    routers (health, auth-context)
app/workers/   celery app + task stubs
alembic/       migrations (schema + RLS)
scripts/       seed, export_openapi
tests/         unit + integration
```
