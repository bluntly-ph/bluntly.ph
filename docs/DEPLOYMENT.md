# Deploying to Vercel

Two services from one repo, wired by `vercel.json`:

| Service | Root | Notes |
|---|---|---|
| `frontend` | `.` | Next.js 16 |
| `backend` | `backend` | FastAPI |

**`vercel.json` takes no comments.** It is validated against a strict schema and
a `"//"` key fails the build with *"should NOT have additional property `//`"* —
which fails silently as a skipped deploy if you are relying on the git
integration. Anything explanatory goes here instead.

## Region

`"regions": ["sin1"]` (Singapore), because Supabase lives in `ap-southeast-1`.
Without it functions default to `iad1` (Virginia) while the database sits in
Singapore, so every query crosses the Pacific twice. Measured 2026-08-10:
`/health` 0.44s but any DB-backed call 1.7–2.9s, while the query itself executes
in 1.9ms. `sin1` is also nearest the PH audience.

## Routing

The rewrites send to the backend exactly the paths FastAPI actually mounts, so
no prefix rewriting is involved and a URL means the same thing in production as
it does locally:

| Source | Service | Why |
|---|---|---|
| `/api/v1(/.*)?` | backend | Every API route. Matches the FastAPI mount verbatim. |
| `/r/(.*)` | backend | The affiliate referral redirect. **Public links point here** — if it lands on the frontend, every affiliate click 404s and no commission is ever attributed. |
| `/health` | backend | Uptime checks. |
| `/(.*)` | frontend | Everything else, including `/api/bff/*`. |

Order matters: the catch-all is last. `/api/bff/*` is the frontend's own
forwarder and deliberately does **not** match `/api/v1`, so it keeps attaching
the session token instead of being handed straight to the backend.

An earlier draft routed `/api/backend/*` to the backend, which meant callers had
to write `/api/backend/api/v1/…` — a doubled prefix that FastAPI would 404 —
and, worse, left `/r/{review_id}` falling through to the frontend.

## Environment variables

Set these in the Vercel project — **not** in `vercel.json`, which is committed.

### Frontend service

| Variable | Value | Why |
|---|---|---|
| `API_URL` | the backend service's origin | Server-only. Deliberately **not** `NEXT_PUBLIC_`: the browser never calls the API directly, so publishing the origin into client bundles buys nothing. |
| `SESSION_COOKIE_NAME` | `bluntly_session` | Optional; this is the default. |

`NEXT_PUBLIC_API_URL` still works as a fallback for existing local setups, but
production should set `API_URL`.

Because `/api/v1` is now routed to the backend on the same origin, `API_URL` can
simply be the site origin (`https://bluntly.ph`) — server-side calls then travel
frontend → rewrite → backend. Pointing it straight at the backend service's own
origin skips that hop and is preferred if you have the URL; both work, and
nothing else in the app changes either way. Locally it stays
`http://localhost:8000`.

### Backend service

| Variable | Notes |
|---|---|
| `APP_ENV` | `production` — turns on the boot gate below |
| `JWT_SECRET` | ≥ 32 random chars |
| `PII_HASH_SALT` | strong random; one-way salt for `sessions.ip_hash` |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` | |
| `SUPABASE_CONNECTION_STRING_SESSION_POOLER` | migrations, port **5432** |
| `SUPABASE_CONNECTION_STRING_TRANSACTION_POOLER` | runtime, port **6543** |
| `USE_SUPABASE` | `true` |
| `CORS_ORIGINS` | the real origin, e.g. `https://bluntly.ph` |
| `REDIS_URL` | a reachable Redis — see below |
| `EMAIL_PROVIDER` | `resend` |
| `RESEND_API_KEY`, `EMAIL_FROM` | |
| `PAYOUT_PROVIDER`, `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_BASE_URL` | |

**The pooler split is not optional.** Session mode caps at ~4 concurrent
clients, so serving runtime traffic from it returns 500s under any real load
(`docs/DEVIATIONS.md` #57). Migrations need session mode because
`ALTER TYPE … ADD VALUE` runs in an autocommit block, which transaction mode
cannot provide.

## The boot gate

`Settings.production_issues()` refuses to serve production traffic on an unsafe
config. Run it against the deployment env before shipping:

```bash
cd backend && .venv/Scripts/python -c "
from app.core.config import Settings
for i in Settings(app_env='production').production_issues(): print('-', i)"
```

It currently blocks on: a weak `JWT_SECRET` or `PII_HASH_SALT`; `CORS_ORIGINS`
containing `*` or pointing at localhost; `REDIS_URL` pointing at localhost;
`EMAIL_PROVIDER=console`; `resend` without a key; a runtime URL on the session
pooler; and a threadpool larger than the DB pool.

## Redis is required in practice

`core/rate_limit.py` **fails open** — a Redis outage logs and allows. The OTP
send and verify caps live in Postgres so they survive that, but nothing else
does: without Redis, login and register brute-force protection is silently
absent. Provision managed Redis and set `REDIS_URL`.

## Known gaps

- **No CI.** There is no `.github/workflows`; nothing runs the 206 backend tests
  or the frontend build on push.
- **`EMAIL_FROM=onboarding@resend.dev`** is an accepted owner decision. Resend
  answers **403** for any recipient other than the account owner, so sign-up
  only completes for that address until a domain is verified. A shared sender
  also has no SPF/DKIM alignment with `bluntly.ph`, which hurts inbox placement.
- **Rotate the PayPal and Resend credentials** before going live; both were
  shared in a chat transcript.
