# Load test results (M3 slice 14)

Profile: `backend/loadtest/locustfile.py` — 70% public reads, 15% authenticated
browse, 10% review submit, 5% moderator queue.

```bash
cd backend
# local compose (full target run)
locust -f loadtest/locustfile.py --host http://localhost:8000 \
       --users 100 --spawn-rate 10 --run-time 5m --headless
# Supabase-backed instance — keep it CAPPED (shared session pooler)
locust -f loadtest/locustfile.py --host http://localhost:8001 \
       --users 25 --spawn-rate 5 --run-time 3m --headless
```

Set `LOADTEST_MOD_TOKEN` to a moderator's JWT or the queue user skips itself
(promotion is a DB action). The run **exits non-zero if a target is missed**, so
it works as a gate, not just a wall of numbers.

## Targets (pinned by the M3 plan)

| Target | Result |
|---|---|
| p95 read < 500 ms | ✅ 73 ms aggregate (local, 100 users) |
| p95 write < 1 s | ✅ 110 ms (`POST /reviews`) |
| error rate < 0.1% | ✅ 0.0101% |
| zero 5xx | ✅ none |

## Run 1 — local compose, 100 users, 5 min, 19,767 requests

| Endpoint | p50 | p95 | p99 |
|---|---|---|---|
| `GET /reviews?sort=wilson` | 13 ms | 31 ms | 130 ms |
| `GET /reviews` | 13 ms | 33 ms | 190 ms |
| `GET /products/{id}` | 10 ms | 27 ms | 110 ms |
| `GET /tokens/balance` | 10 ms | 26 ms | 160 ms |
| `GET /requests` | 12 ms | 34 ms | 160 ms |
| `POST /reviews` | 70 ms | 110 ms | 540 ms |
| `GET /health` | 5 ms | 11 ms | 96 ms |
| **Aggregated** | **12 ms** | **73 ms** | **330 ms** |

Errors: 2 / 19,767 (0.0101%) — both client-side socket aborts on the Windows
load generator (`RemoteDisconnected`, `WinError 10053`). **No server errors.**

## Run 2 — Supabase (session pooler, ap-southeast-1), 25 users, 3 min, 2,632 requests

| Endpoint | p50 | p95 |
|---|---|---|
| `GET /reviews?sort=wilson` | 150 ms | 160 ms |
| `GET /products/{id}` | 140 ms | 150 ms |
| `POST /reviews` | 460 ms | 490 ms |
| `GET /health` (DB-free) | 3 ms | 6 ms |
| **Aggregated** | **150 ms** | **460 ms** |

Errors: **0.0000%**. The ~150 ms floor on every DB-backed read is the round trip
to Supabase; `/health` (which touches no DB) stays at 3 ms, which isolates it as
network, not application, cost.

## What the load test found (and what was fixed)

**A real defect: one slow endpoint could 500 every other endpoint.**
The first 100-user run produced 40 × `QueuePool limit of size 5 overflow 5
reached` and HTTP 500s on `/reviews`, `/products/{id}`, `/auth/me` — endpoints
with nothing wrong with them. Cause: `THREADPOOL_TOKENS` admitted **40**
concurrent sync requests per worker while the pool held **10** connections. Every
sync endpoint holds its session for the whole request, so the surplus queued on
the pool and expired at `DB_POOL_TIMEOUT`.

Fix (`app/core/config.py`): pool raised to 10+10 per worker and
`THREADPOOL_TOKENS` set to 20, with the invariant **`THREADPOOL_TOKENS <=
DB_POOL_SIZE + DB_MAX_OVERFLOW`** now enforced by `production_issues()` — the app
refuses to boot in production if the two drift apart again. Connection budget:
`2 workers × 20 + ~4 Celery = 44`.

## ⚠️ Known hot spot — the moderator queue (not fixed; needs an owner decision)

| | local | Supabase |
|---|---|---|
| `GET /admin/review-queue` p95 | ~0.9 s | **9 s** |

Measured cost: the advisory fraud signals run **5 queries per card, ~37 ms per
card**, so a 25-card page is ~124 queries and holds one connection for ~915 ms
locally — and ~8–9 s against Supabase, where each of those queries pays a network
round trip.

It does not breach the pinned targets (it is 5% of traffic, a handful of
moderators, and the aggregate p95 is 460 ms), and with the pool fix it no longer
starves other endpoints. But a 9-second admin screen is poor, and the fix —
batching the per-card signals into set-based queries, or computing them
asynchronously — is real design work. Per the M3 plan ("deeper perf work would be
a new owner conversation"), it is recorded here rather than improvised.

**Cheap mitigations available now, no code change:** page the queue with
`?limit=10` (≈2.5× faster), or run the API closer to the database.
