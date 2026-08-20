# Bluntly.ph

A verified product-review platform for Filipino online shoppers. Live at
**https://www.bluntly.ph**.

It exists because the review systems built into Shopee (~51% of PH e-commerce
traffic) and Lazada (~24%) require no proof of purchase, enforce no
completeness standard, and reward volume over substance. Bluntly's argument is
*structural incentive alignment*: honest reviews are made more **visible**
(time-decayed Wilson ranking with velocity detection), more **rewarded**
(a 40/30/30 commission split plus an Honesty Fund that pays for honest negative
reviews), and more **trusted** (proof-of-purchase verification, a seven-layer
fraud-deterrence framework, human moderation) than fake ones.

A capstone deliverable (PUP CCIS, June 2026), developed in consultation with
Laban Konsyumer Inc., evaluated against ISO/IEC 25010:2011.

---

## ⚠️ Read this before running anything

**This project has one production database, and until recently every default
pointed at it.** On 2026-08-19 the full test suite was run against production
and created hundreds of fixture reviews on the live site.

Production is now refused in code (`backend/app/core/env_guard.py`) for
pytest, every writing script, Alembic, **and** the local dev launcher:

- **`npm run dev:all` stops** if it resolves to production, and uses
  `backend/.env.test` when that file exists. `-AllowProduction` is the
  deliberate escape hatch for read-only debugging.
- **`alembic` refuses without an explicit target.** Use `-x test=1` or
  `-x allow_production=1`.

Do not assume the guard is decorative: it has already caught three real
mistakes, including a launcher that announced "test" while connected to
production because PowerShell deletes a variable assigned an empty string.

Full detail, including the expand→contract migration rules, is in
[`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md). Read it before your first
migration.

---

## Architecture

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 App Router (Turbopack), React 19, TypeScript, Tailwind v4 bridged to design tokens |
| Backend | FastAPI + SQLAlchemy + Alembic, deployed as a Vercel Python function |
| Database | PostgreSQL 17 on Supabase (`ap-southeast-1`), 28 tables, RLS on every table |
| Auth | **App-native**, not Supabase Auth (ADR-010/011): passwordless email OTP, Argon2id, HS256 JWT |
| Storage | Supabase Storage — three public buckets plus a **private** `review-receipts` |
| Jobs | Celery: PII retention, nightly Wilson re-decay, monthly Honesty Fund |
| Email | Resend/SES from the verified subdomain `mail.bluntly.ph` |
| Hosting | Vercel; `main` auto-deploys to production |

The browser talks only to the Next server, which calls FastAPI server-side with
a token held in an httpOnly cookie (`lib/dal.ts`). Client-side mutations detour
through a BFF proxy at `app/api/bff/[...path]`, so the browser never holds the
API token.

**No scraping, ever.** Marketplace ToS prohibit it, and the owner ruled it out
permanently on 2026-07-15. Affiliate data arrives by manual CSV import of the
owner's own reports; price data is community-submitted. There is no Scrapy, no
proxy rotation, and no headless browser anywhere in the codebase.

`AGENTS.md` warns that this Next.js version differs from what most tooling
expects — check `node_modules/next/dist/docs/` before assuming an API.

---

## Prerequisites

- Node.js 22+
- Python 3.12 with a virtualenv at `backend/.venv`
- Access to the Supabase project (or the test project, below)

## Environment setup

```bash
cp .env.example .env                       # frontend + shared
cp backend/.env.example backend/.env       # backend (optional; root .env is read too)
```

`Settings` reads `../.env`, then `backend/.env`, then `backend/.env.test` —
later files win, and real environment variables win over all of them. Never commit an `.env` — only the `.example` templates are tracked,
via explicit `!` negations at the end of `.gitignore`.

## Local development

```bash
npm install
npm run dev:all      # Next + FastAPI together
npm run dev:stop
```

Open http://localhost:3000. With `backend/.env.test` present this targets the
test project; without it, the launcher refuses to start rather than silently
using production.

## Test environment

Tests run against a separate Supabase project (`bluntly-ph-test`), never
production. One-time setup:

```bash
cp backend/.env.test.example backend/.env.test
# fill the two FROM DASHBOARD values, then one command does the rest:
cd backend && .venv/Scripts/python -m scripts.bootstrap_test_env
```

Until the test database password is filled in, DB-backed tests **skip cleanly**
rather than falling back to production.

## Running tests

```bash
cd backend && .venv/Scripts/python -m pytest    # backend
npx tsc --noEmit                                # typecheck
npm run lint                                    # lint
npm run build                                   # production build
npm run test:e2e                                # Playwright, 5 browser profiles
```

First Playwright run on a new machine needs
`npx playwright install firefox webkit`.

## Migrations

```bash
cd backend
.venv/Scripts/python -m scripts.check_migration_safety   # ALWAYS run this first
.venv/Scripts/python -m alembic -x test=1 upgrade head   # test project
.venv/Scripts/python -m alembic -x allow_production=1 upgrade head
```

Contracting changes (`DROP COLUMN`, renames, `NOT NULL`) need
expand → deploy → backfill → verify → switch → contract, across more than one
deployment. A destructive-first migration took the API down on 2026-08-19;
`docs/ENVIRONMENTS.md` has the rules.

## Deployment

`main` auto-deploys to Vercel. Migrations are **not** part of the deploy — they
are applied by hand, deliberately, which is why they need an explicit target.

## Deeper documentation

| Document | What it covers |
|---|---|
| [`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md) | Environment map, test isolation, migration safety |
| [`docs/01-bluntly-ph-PRD.md`](docs/01-bluntly-ph-PRD.md) | Requirements (FR-1…FR-9), NFRs, open ambiguities |
| [`docs/MILESTONES.md`](docs/MILESTONES.md) | M1–M3 scope and verification |
| [`docs/FRONTEND_MILESTONES.md`](docs/FRONTEND_MILESTONES.md) | FE-M1–FE-M5 |
| [`docs/schema.md`](docs/schema.md) | Data dictionary, storage bucket classification, receipt access rules |
| [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) | Where the build departs from the original spec, and why |
| [`docs/adr/`](docs/adr/) | 15 architecture decision records |
| [`qa/README.md`](qa/README.md) | Bug tracker, retest procedures |
| [`AGENTS.md`](AGENTS.md) | Next.js version warning |
