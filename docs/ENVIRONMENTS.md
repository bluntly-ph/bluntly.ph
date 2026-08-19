# Environments, test isolation, and safe migrations

Written after two incidents on 2026-08-19, both caused by the same root fact:
**this project had exactly one database, and it was production.**

1. The full pytest suite was run against it and created hundreds of fixture
   reviews on the live site.
2. A destructive migration was applied before the code that tolerated it was
   deployed, and the production API returned 500 for several minutes.

Neither was a mistake of carelessness — the repository made both the default
behaviour. What follows is the arrangement that stops them.

---

## The map

| Environment | App/API | Database | Storage | Safe for destructive tests? |
|---|---|---|---|---|
| **Production** | `www.bluntly.ph` (Vercel, `main` auto-deploy) | Supabase `byobedbhodhvocgrkrse` | `avatars`, `product-images`, `review-photos` (public); `review-receipts` (private) | **No** |
| **Preview** | none configured | — | — | n/a |
| **Local development** | `npm run dev:all` | **production** (repo-root `.env`) | production | **No** — see the warning below |
| **Backend tests** | pytest | Supabase `miysywhcdqkoniaibglx` (`bluntly-ph-test`) via `backend/.env.test` | that project's buckets | **Yes** |
| **Frontend tests** | none exist | — | — | n/a |
| **E2E (Playwright)** | local dev server | whatever the dev server uses | same | read-only by design |
| **CI** | none configured | — | — | n/a |

Two rows deserve emphasis.

**Local development refuses to start against production.** `npm run dev:all`
reads the repo-root `.env`, so clicking around the local app used to write to
the live database. The launcher now resolves the target first and stops:

```
REFUSING TO START - local dev is pointed at PRODUCTION
```

`scripts/dev.ps1 -AllowProduction` is the deliberate escape hatch for read-only
debugging; it prints a loud banner every time and is never persisted.

The guard sits in the launcher, not the application, because the deployed
production function obviously still has to boot with production configuration.

When `backend/.env.test` exists the launcher loads it into **both** child
processes, so the frontend and backend are always one environment. A frontend
on test with a backend on production is worse than either alone: every symptom
points at the wrong half.

**E2E is read-only and must stay that way.** All five specs assert on public
read surfaces and client-side behaviour; none issues a write. If you add a spec
that submits a review, votes, or uploads, point the dev server at the test
project first. A writing E2E test against the production dev server is the
original incident wearing a different hat.

---

## Test isolation

The rule is enforced in code, not by convention:

> Running any automated test command must never mutate production.

`backend/app/core/env_guard.py` decides what "production" means, and it does so
from **what the connection actually points at** rather than from an environment
name. That distinction is the whole design. The repo-root `.env` sets
`USE_SUPABASE=true` and never sets `APP_ENV`, so `app_env` defaults to `"local"`
while every connection goes to production — a guard trusting the environment
name would have waved the suite straight through.

Signals checked, any one of which means production:

- an env value referencing the production Supabase project ref
- an env value pointing at `bluntly.ph` / `www.bluntly.ph`
- `APP_ENV=production`

It resolves those values from the **same env files pydantic-settings reads**
(`.env`, `backend/.env`, `backend/.env.test`) with real environment variables
taking precedence — not from `os.environ` alone. An earlier draft read only the
process environment, saw nothing (the credentials live in a file), and reported
"unrecognised"; anyone who then set the test marker would have gone straight to
production. Reading the files is what makes the guard real.

It **fails closed**: a target that has not positively identified itself as a
test environment is treated as production. Assuming "unknown means safe" is how
a guard quietly stops guarding.

### Where it runs

- **pytest** — `tests/conftest.py` loads `backend/.env.test` and runs the guard
  *before importing anything from `app`*, because importing `app.db.session`
  opens an engine. Collection aborts with exit code 1 and no test runs.
- **Scripts** — every writing script calls `guard_cli()` inside its
  `if __name__ == "__main__"` block, so it prints its target and then refuses.

### The production override

Three scripts legitimately run against production and accept
`--allow-production`: `hide_test_content`, `migrate_receipts`,
`seed_product_images`. Everything else — the seeders, `reset_and_seed`, the
smoke/verify scripts — has no override at all, because there is no good reason
to point them at the live site.

The override is a **command-line flag, never an environment variable**, so it
cannot be left switched on in a shell profile and forgotten.

`reset_and_seed` deserves its own sentence: it `TRUNCATE`s every content table
and deletes users. Before this work it had no guard whatsoever and a single
`python -m scripts.reset_and_seed` would have wiped the live site.

### Alembic is guarded too

`alembic upgrade head` reads the repo-root `.env`, which is production. That is
how a migration intended for the test database silently ran against production
during this work — a near-miss that did no harm only because production was
already at head. pytest and the scripts were guarded; alembic was the remaining
door, and it is the one that applies schema changes.

The target is now printed on every invocation and must be chosen:

```bash
alembic -x test=1 upgrade head              # the test project
alembic -x allow_production=1 upgrade head  # production, deliberately
alembic upgrade head                        # REFUSED — pick one
```

Nothing in the deploy pipeline runs alembic (Vercel builds the app; migrations
are applied by hand), so requiring an explicit choice breaks no automation.

### Setting up the test environment

```bash
cp backend/.env.test.example backend/.env.test
# fill in the two FROM DASHBOARD values, then:
cd backend && .venv/Scripts/python -m alembic -x test=1 upgrade head
cd backend && .venv/Scripts/python -m pytest
```

**The database password must come from the dashboard.** This is the one step
that cannot be automated, and it was investigated properly before being called
a blocker:

- the test project (`bluntly-ph-test`, `miysywhcdqkoniaibglx`) exists and is free
- the Supabase MCP exposes no password-reset tool
- `ALTER USER postgres WITH PASSWORD …` fails: on Supabase `postgres` is not a
  superuser and cannot alter a privileged role
- a dedicated `bluntly_test` login role **was** created and **does** connect
  through the session pooler — but migration `0002_rls_policies` fails for it
  with `permission denied for schema auth`, because its policies call
  `auth.uid()` and USAGE on the `auth` schema can only be granted by
  `supabase_admin`

Remaining step: **Supabase dashboard → `bluntly-ph-test` → Settings → Database →
Reset database password**, then paste the session-pooler connection string into
`SUPABASE_CONNECTION_STRING_SESSION_POOLER` in `backend/.env.test` and set
`USE_SUPABASE=true`. After that, the two commands above are all that remain.

Until then `backend/.env.test` leaves the connection blank on purpose, so
DB-backed tests **skip cleanly** rather than failing against a half-privileged
role.

`backend/.env.test` is gitignored. The `.example` template is not — `.gitignore`
carries explicit `!` negations at the end of the file, because `.env*` appears
twice and a later ignore rule overrides an earlier negation.

---

## Safe migrations: expand → migrate → contract

The 2026-08-19 outage: migration `0023` dropped `reviews.receipt_url` and was
applied while the deployed build still selected that column. Every review read
500'd until the new build shipped. The migration was correct; the **rollout
order** was not.

Before writing a migration, classify it:

| Class | Example | Rollout |
|---|---|---|
| **Additive** | new nullable column, new table, new index | migrate any time; deploy after |
| **Backfill** | populate a new column | migrate after the code that writes both |
| **Contracting** | `DROP COLUMN`, `DROP TABLE`, rename, narrowing type, `NOT NULL` | **needs the full dance below** |
| **Destructive data** | `TRUNCATE`, `DELETE`, rewriting rows | never in a migration; use a guarded script |

For anything contracting:

1. **Expand** — add the new column/table. Old code keeps working.
2. **Deploy** code that tolerates *both* shapes (reads old, writes both).
3. **Backfill** the data.
4. **Verify** in production.
5. **Switch** reads to the new representation. Deploy.
6. **Contract** — drop the old column in a *later* migration, once nothing
   deployed references it.

Steps 1–2 and 5–6 are separate deployments. If the correct rollout needs more
than one deploy, do more than one deploy. `0023` collapsed all six steps into
one and took the API down.

### The pre-flight check

`backend/scripts/check_migration_safety.py` scans pending migrations for
contracting operations and prints what it finds, with the rollout each implies.
It is advisory — it prints and explains, it does not block, because a tool that
blocks legitimate work gets disabled. Run it before applying anything:

```bash
cd backend && .venv/Scripts/python -m scripts.check_migration_safety
```

### Deployment order for a contracting change

```
code compatible with both schemas
  → deploy
  → migrate/backfill
  → verify production
  → remove the old schema in a later migration
```

---

## Storage classification

See `docs/schema.md` for the bucket table and the receipt access rules. The
short version: buckets are classified by **audience**, not by uploader, and
proof-of-purchase evidence is never public.
