# Release acceptance runbook

Everything between "owner credentials arrive" and "contract ready or not",
written so another competent engineer can execute it without reconstructing a
plan. Each section states what unblocks it, the exact commands, what a pass
looks like, and what to do when it fails.

Four things are blocked on the owner and nothing else is. They are
independent — do them in any order, or in parallel.

| Blocker | Unblocks | Owner action |
|---|---|---|
| **A. Test database** | 125 backend tests, 58 milestone checks, moderator a11y spec | a Supabase password *or* a Docker permission |
| **B. GitHub `workflow` scope** | CI activation | re-authorize the credential |
| **C. PayPal sandbox** | FR-6 contractual acceptance | sandbox client id + secret |
| **D. Production env vars** | rate limiting, and every production self-check | set `APP_ENV` and `REDIS_URL` in Vercel |

> **The verdict cannot be `CONTRACT READY` until C is executed.** FR-6 makes
> PayPal payouts contractual, so its acceptance has to actually happen — not be
> inferred from the mocked boundary tests, however complete those are.

---

## A. Test database

Two routes. Either is sufficient; the Docker one needs no Supabase dashboard
access.

### A1 — Supabase (recommended if the dashboard is to hand)

1. Supabase dashboard → project **`bluntly-ph-test`** (`miysywhcdqkoniaibglx`)
   → **Settings → Database → Reset database password**.
2. Copy the **session pooler** connection string (port **5432**, user
   `postgres.miysywhcdqkoniaibglx`).
3. `cp backend/.env.test.example backend/.env.test` if it does not exist, then
   set in that file — **never paste a password into chat or a terminal
   transcript**:
   ```
   USE_SUPABASE=true
   SUPABASE_CONNECTION_STRING_SESSION_POOLER=<the string, password included>
   SUPABASE_SECRET_KEY=<Settings → API → service_role>
   ```

`backend/.env.test` is gitignored. Confirm with `git check-ignore backend/.env.test`.

### A2 — Docker (no Supabase access needed)

The repo already carries the stack. Docker's engine runs on this machine but
its CLI is permission-denied on `npipe:////./pipe/dockerDesktopLinuxEngine`.

1. Fix the Docker Desktop permission (add the user to `docker-users`, or run
   Docker Desktop as the same user), until `docker ps` works.
2. `cd backend && docker compose up -d postgres`
3. In `backend/.env.test`:
   ```
   USE_SUPABASE=false
   DATABASE_URL=postgresql+psycopg://bluntly:bluntly@localhost:5432/bluntly
   ```

### Then, either route — one command

```bash
cd backend && .venv/Scripts/python -m scripts.bootstrap_test_env
```

It validates the target, **refuses production**, migrates from zero to head,
verifies the revision, runs pytest, runs the 58 milestone checks, and prints a
per-stage summary. It exits non-zero if any stage fails.

**Pass looks like:** every stage `[PASS]`, pytest reporting ~341 passed with
**0 skipped** (the 125 current skips are all `requires_db`), and
`MILESTONE CLAIMS: 58/58 verified`.

**If it stops at `NOT READY`** the connection string still points at
localhost — step 3 did not take effect.

**If pytest fails**, do not convert failures to skips. The DB-backed tests have
never executed against a real Postgres, so a first run may surface genuine
fixture ordering problems; fix them.

**Then run the moderator accessibility spec**, which has never executed:

```bash
cd backend && .venv/Scripts/python -m scripts.mint_e2e_moderator
# copy the printed command:
E2E_MODERATOR_TOKEN=<token> npx playwright test e2e/moderator-a11y.spec.ts
cd backend && .venv/Scripts/python -m scripts.mint_e2e_moderator --cleanup
```

---

## B. CI activation

1. Re-authorize the GitHub credential with the **`workflow`** scope. Without it
   GitHub rejects any push touching `.github/workflows/`, with:
   `refusing to allow an OAuth App to create or update workflow … without workflow scope`.
2. ```bash
   mkdir -p .github/workflows
   git mv docs/ci/ci.yml .github/workflows/ci.yml
   git commit -m "ci: activate the GitHub Actions workflow"
   git push
   ```
3. Optional, for the DB job only — **Settings → Secrets and variables →
   Actions**: `TEST_SUPABASE_SESSION_POOLER`, `TEST_SUPABASE_URL`,
   `TEST_SUPABASE_SECRET_KEY`. Never production values.
4. Watch the first run. `guard`, `backend` and `frontend` must pass with no
   secrets at all. `backend-db-tests` skips with a notice until step 3.

**Pass looks like:** four jobs, three green without secrets, and the `guard`
job proving a simulated production target is *refused*.

---

## C. PayPal sandbox acceptance (FR-6)

Everything up to the provider boundary is already verified by mocked tests
(`backend/tests/test_payouts_api.py`). What follows is the part that cannot be
mocked.

### Setup

Set in the environment used for the run — **names only, never values in a
transcript, screenshot, or log**:

```
PAYOUT_PROVIDER=paypal_sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=…
PAYPAL_SECRET=…
```

Run against the **isolated test environment**, never production: this creates
users, wallet balances and payout batches.

### Scenarios

| # | Scenario | Expected |
|---|---|---|
| 1 | Wallet ₱299.99, run the scheduler | Not selected. Below `PAYOUT_MIN_PHP` |
| 2 | Wallet exactly ₱300.00 | Selected, batch submitted |
| 3 | Wallet ₱300.01 | Selected |
| 4 | No payout account set | Not selected; no provider call |
| 5 | Provider returns SUCCESS, then refresh | Payout `paid`, wallet debited once |
| 6 | Provider returns PENDING, then refresh | Stays `processing`; no double debit |
| 7 | Provider returns FAILED/UNCLAIMED | `failed`, wallet **refunded once** |
| 8 | Cancel a scheduled payout | `cancelled`, wallet refunded once |
| 9 | Run the scheduler twice in one batch window | No second payout — `uq_payout_user_batch` |
| 10 | Refresh the same batch twice | State settles once; no double debit or refund |
| 11 | Wrong credentials | Batch stays `scheduled`, no crash |
| 12 | `PAYOUT_PROVIDER=paypal_live` with a sandbox URL | Startup refuses (`production_issues`) |

Scenarios 9–12 are already covered by mocked tests; re-run them live to confirm
the real provider does not change the shape.

### Evidence to capture

Batch ids, payout ids, status transitions, and wallet balance before/after.
**Never** capture access tokens, the client secret, or full provider response
bodies — the adapters deliberately keep those out of errors and logs, and a
screenshot would undo that.

**FR-6 is verified when** 1–8 behave as tabled and no wallet is debited or
refunded twice.

---

## D. Production configuration

**Found by audit on 2026-08-20, and the only finding here that is live in
production right now.**

Fourteen consecutive failed logins from one address returned 401 and never 429,
against a configured limit of ten per minute. Login, register, OTP request, OTP
verify, voting, reporting and commenting are all unthrottled.

Two settings are involved, and both are absent from the repository:

| Variable | Effect of it being unset |
|---|---|
| `REDIS_URL` | The limiter reaches for `localhost`, fails, and allows. It is designed to fail open so a Redis outage cannot break login — but with nothing configured, open is the *normal* mode. |
| `APP_ENV` | `production_issues()` refuses to start the app on a wildcard CORS origin, a localhost Redis, a placeholder PII salt or a weak postback secret — and `main.py` only runs it when `APP_ENV=production`. The app is up, so that check is not running. |

### What the code now does about it

Migration `0028` adds `rate_limit_counters`, and the limiter tries Redis first,
Postgres second, and only falls open if both are unreachable — logged at
`warning` rather than `info`. Postgres was chosen over provisioning Redis
because it is already the system of record and already on the request path; a
counter does not justify a second piece of paid infrastructure.

**This does nothing until `0028` is applied.** Until then the table is missing,
the fallback returns nothing, and the limiter still allows — the only change
being that it now says so loudly.

### Steps

1. Apply the migrations: `cd backend && alembic -x allow_production=1 upgrade head`
   (brings production to `0028`; `0027` also relabels the product categories).
2. Confirm the limiter enforces — eleven failed logins for a nonexistent
   account from one address should produce a `429`:
   ```bash
   for i in $(seq 1 12); do
     curl -s -o /dev/null -w "%{http_code} " -X POST        -d "username=probe-$(uuidgen)@example.invalid&password=x"        https://www.bluntly.ph/api/v1/auth/login
   done; echo
   ```
3. Optionally set `REDIS_URL` in Vercel to restore the faster primary path.
4. **Last**, once every value in `.env.example` is real in Vercel, set
   `APP_ENV=production`. Do this last deliberately: the app will refuse to boot
   if any check fails, and that refusal is the point.

---

## E. Final release verification

Once A, B and C are done, in this order:

```bash
# 1. Backend, with the isolated DB — expect 0 skips
cd backend && .venv/Scripts/python -m scripts.bootstrap_test_env

# 2. Frontend
npx tsc --noEmit && npm run lint && npm run build

# 3. Browsers — SERIALLY. Five engines in parallel exhausted this host once and
#    produced 180 spurious failures; serial runs are just as valid.
for p in chromium firefox webkit mobile-chrome mobile-safari; do
  npx playwright test --project=$p --workers=1
  npm run dev:stop
done

# 4. Migration safety, before any further schema change
cd backend && .venv/Scripts/python -m scripts.check_migration_safety --all
```

**5. Production smoke** — read-only, no fixtures:

```bash
for u in / /search /categories /compare /questions /requests /membership \
         /api/v1/reviews/feed?limit=6 /api/v1/products?limit=5; do
  curl -s -o /dev/null -w "%{http_code} $u\n" "https://www.bluntly.ph$u"
done
```

**6. Security smoke** — admin routes 401 anonymously; the feed carries no
`receipt_url`, `receipt_key`, `password_hash`, `payout_account` or
`affiliate_link`; the private receipt bucket refuses anonymous access; all six
security headers present; authenticated responses `private, no-store`.

**7. Requirement matrix** — every FR marked `VERIFIED COMPLETE` or
`BLOCKED EXTERNALLY` with named evidence. No `needs retest`.

---

## Rollback and incident response

Classify every production change before making it:

| Class | Rollback |
|---|---|
| Code-only, backward compatible | `git revert`, redeploy |
| Additive schema | Usually leave it; additive changes break nothing |
| Data migration | Restore from the export taken beforehand |
| **Contracting schema** | **Fix forward.** A downgrade that drops the new column loses data |

**The rule that both outages came from:** never apply a contracting migration
before the code that tolerates it is deployed. `0023` dropped
`reviews.receipt_url` and `0024` dropped `users.seller_trust_score` while the
running build still selected them, and every read of those tables 500'd until
the new build shipped. Search the exact **column** names a migration touches,
not the concept — the second outage happened because a search for
`seller_reviews` did not match `users.seller_trust_score`.

Fixture cleanup exports live outside the repository (they contain real user
rows) — see the manifest written alongside them. Restoring means inserting the
per-table JSON in the manifest's order, parents before children.

**Never run against production:** `reset_and_seed` (no override exists),
`verify_milestones` (writes fixtures, no cleanup), `pytest`, or `api_smoke`.
The guards refuse all of them; the guards are not the reason not to.
