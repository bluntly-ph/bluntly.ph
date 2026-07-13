# Production Readiness — Milestone 1

Checklist and runbook to deploy the M1 backend against **Supabase Postgres** in
production. The app fails fast on startup if a hard requirement is unmet
(`Settings.production_issues()` in `app/core/config.py`).

## 1. Required environment (production host)

```
APP_ENV=production
ENABLE_DOCS=false                # optional: hide /docs in prod
JWT_SECRET=<64+ char random>     # python -c "import secrets;print(secrets.token_urlsafe(48))"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=https://app.bluntly.ph   # NOT '*'

# Supabase (prefer the session-pooler string; IPv4 + reachable)
USE_SUPABASE=true
SUPABASE_CONNECTION_STRING_SESSION_POOLER=<session pooler string, see §2>
SUPABASE_CONNECTION_STRING=<direct string, optional>
DB_SSLMODE=require
SUPABASE_URL=... SUPABASE_SECRET_KEY=... SUPABASE_PUBLISHABLE_KEY=...

REDIS_URL=redis://<managed-redis>:6379/0

# AI critique (optional; defaults to a no-key stub)
AI_PROVIDER=stub                 # or claude / openai
ANTHROPIC_API_KEY=...            # if AI_PROVIDER=claude
```

**Hard startup checks (production):** strong `JWT_SECRET` (≥32 chars, not the dev
default), a non-localhost DB (or `USE_SUPABASE=true`), and `CORS_ORIGINS` without
`*`. Any failure raises on boot.

## 2. Supabase connection string — direct vs pooler (IMPORTANT)

Supabase offers two endpoints:

| Endpoint | Host | Port | IP | Use for |
|---|---|---|---|---|
| **Direct** | `db.<ref>.supabase.co` | 5432 | **IPv6-only** | Only from IPv6-capable hosts |
| **Session pooler** | `aws-<n>-<region>.pooler.supabase.com` | 5432 | IPv4 | **Migrations + runtime** from IPv4 networks |
| **Transaction pooler** | same pooler host | 6543 | IPv4 | Serverless runtime (auto disables prepared statements) |

> The direct host is **IPv6-only**. On an IPv4-only network (typical local dev,
> many CI/CD runners, some containers) it won't even resolve. **Use the Session
> pooler string** (Dashboard → Project → Connect → *Session pooler*). The app
> auto-applies `sslmode=require`, and disables prepared statements for the
> transaction pooler.

Verify reachability before migrating:

```bash
USE_SUPABASE=true python -m scripts.db_check
```

## 3. Apply schema + seed to Supabase

> **Status:** ✅ Applied to project `byobedbhodhvocgrkrse` on 2026-07-12 via the
> session pooler — 17 tables, 33 RLS policies, tiers/badges/sample data seeded, and
> the live app verified end-to-end (register → me → tiers) against Supabase.

Config prefers `SUPABASE_CONNECTION_STRING_SESSION_POOLER` when set. To (re)apply:

```bash
USE_SUPABASE=true python -m alembic upgrade head    # creates all 17 tables + RLS
USE_SUPABASE=true python -m scripts.seed            # tiers, badges, sample data
USE_SUPABASE=true python -m scripts.db_check        # confirm: public tables = 17
```

RLS policies apply cleanly on Supabase (its built-in `auth.uid()` is used; the
local shim is skipped). Note: the backend connects as the `postgres` role and
enforces RBAC in the API layer, so RLS is defense-in-depth for any *direct*
Supabase access, not the primary control.

## 4. Deploy the app + workers

Container image is `backend/Dockerfile`. Run three processes (see
`docker-compose.yml` for commands):

- **api:** `uvicorn app.main:app --host 0.0.0.0 --port 8000` (front with a TLS
  terminator / load balancer).
- **worker:** `celery -A app.workers.celery_app.celery_app worker`
- **beat:** `celery -A app.workers.celery_app.celery_app beat`

Do **not** run `alembic upgrade` from every replica; run it once as a release step.

### Connection budget & tuning

Endpoints are sync `def` (they run in Starlette's AnyIO threadpool), so each API
process needs a DB connection pool sized against the **Supabase session pooler**
budget, which is shared across the api, Celery worker, and beat. Total connections
≈ `workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) + Celery`.

| Setting | Default | Effect |
|---|---|---|
| `uvicorn --workers` | 2 | API processes per container |
| `DB_POOL_SIZE` | 5 | persistent connections per process |
| `DB_MAX_OVERFLOW` | 5 | burst connections above pool_size per process |
| `DB_POOL_TIMEOUT` | 10s | wait for a connection, then fail fast (not 30s) |
| `DB_POOL_RECYCLE` | 300s | recycle stale connections (pooler-safe) |
| `THREADPOOL_TOKENS` | 40 | AnyIO threadpool ceiling per process (in-flight sync req cap) |

With the defaults: `2 × (5+5) + ~4 (worker/beat) ≈ 24` connections — sized to fit
the session pooler. Scale `--workers` and the pool sizes together and keep the
product under the pooler's max. Note: `/health` is DB-free, so it stays a cheap,
always-green load-balancer probe even if the pool is saturated.

## 5. Post-deploy smoke test

```bash
curl -s https://api.bluntly.ph/health          # {status, product_id, version, timestamp}
# register -> login -> me should round-trip; /docs disabled if ENABLE_DOCS=false
```

## 6. Known gaps / follow-ups (not M1 blockers)
- RLS is dormant given API-layer RBAC; revisit if any client talks to Supabase directly.
- Supabase Storage (proof photos/receipts) is wired for later milestones, not M1.
- Secrets belong in the platform secret store, never committed.
