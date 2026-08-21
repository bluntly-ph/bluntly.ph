# Release acceptance runbook

Everything between "owner credentials arrive" and "contract ready or not",
written so another competent engineer can execute it without reconstructing a
plan. Each section states what unblocks it, the exact commands, what a pass
looks like, and what to do when it fails.

Five things are blocked on the owner and nothing else is, and **E is live** - do that one first. They are
independent — do them in any order, or in parallel.

| Blocker | Unblocks | Owner action |
|---|---|---|
| **A. Test database** | 125 backend tests, 58 milestone checks, moderator a11y spec | a Supabase password *or* a Docker permission |
| **B. GitHub `workflow` scope** | CI activation | re-authorize the credential |
| **C. PayPal sandbox** | FR-6 contractual acceptance | sandbox client id + secret |
| **E. PostgREST containment** | **a live data exposure** | apply `0027`-`0029` to production |
| **F. Production env vars** | rate limiting, and every production self-check | set `APP_ENV` and `REDIS_URL` in Vercel |

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

## B. CI activation — ✅ ACTIVE AND GREEN (2026-08-21)

The workflow lives at `.github/workflows/ci.yml` and runs on every push. The
`workflow` OAuth scope that had blocked it was granted with
`gh auth refresh -h github.com -s workflow`.

First run: four jobs, three green without any secrets, `backend-db-tests`
skipping on its documented condition.

| Job | Result |
|---|---|
| Production guard | green — 44s |
| Backend (no database) | green — 45s |
| Frontend | green — 54s |
| Backend (isolated database) | skipped — `TEST_SUPABASE_SESSION_POOLER not set` |

**It has already earned its place.** The very next push
(`feat(ops): the app reports its own production readiness`) went red: a test
asserted `raise RuntimeError` appeared within 300 characters of a marker line
in `main.py`, and an added comment pushed it outside that window. The behaviour
was untouched, the assertion was a proximity heuristic — but nothing else was
watching, and before CI existed that would have landed silently. Fixed in
`ecf7efa`, which asserts the structure from the parse tree instead.

### Remaining: the isolated-database job

`TEST_SUPABASE_URL` is set. Two more are needed, and both live behind the
Supabase dashboard because neither is retrievable through any API:

```bash
# Supabase → project bluntly-ph-test (miysywhcdqkoniaibglx)
#   Settings → Database → Reset database password  -> session pooler URI
#   Settings → API      → service_role key
gh secret set TEST_SUPABASE_SESSION_POOLER      # paste at the prompt
gh secret set TEST_SUPABASE_SECRET_KEY          # paste at the prompt
```

`gh secret set` reads from the prompt or stdin, so neither value is ever typed
into a chat, a file, or a shell history entry.

The job then runs `scripts.bootstrap_test_env`, which validates the target,
refuses production, migrates the empty test project to head, runs the suite and
the milestone verifier. The test project is **currently empty** — 0 tables, no
`alembic_version` — so its first run builds the schema from scratch.

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

## E. PostgREST containment — ✅ APPLIED AND VERIFIED

**Closed 2026-08-21.** Migrations `0027`–`0030` applied to production; schema
now matches repository head at `0030_tier_share_bounds`.

Verified after application:

| Check | Before | After |
|---|---|---|
| Tables readable by `anon` | 28 | **0** |
| Tables readable by `authenticated` | 28 | **0** |
| Tables readable by `postgres` (the app) | 28 | 29 |
| Tables readable by `service_role` (storage) | 28 | 29 |
| Anonymous PostgREST, 8 sampled tables | `200` with rows | **`401 permission denied`** |
| Application pages + API, 17 checks | — | all pass |
| Public product image | served | served |
| Private receipt bucket | refused | refused |

**One residual, and it cannot be fixed from here.** `supabase_admin`'s default
privileges still grant new tables to `anon`, and only `supabase_admin` may
change them — neither the `postgres` role nor the SQL editor can. Migrations
run as `postgres` and are unaffected, so anything created the normal way is
clean. A table created through the **dashboard UI** would not be.

`check_invariants` now covers exactly this: two checks assert that no table in
`public` is readable by `anon` or `authenticated`. A dashboard-created table
shows up there immediately.

The original finding, kept for the record:

An anonymous caller holding the Supabase publishable key — public by design —
can read table rows directly over PostgREST, past the API and every serializer
in it. 17 of 28 tables carry a `USING (true)` SELECT policy, which returns
every row *and every column*:

    answers  badges  earn_eligible_votes  membership_tiers  price_history
    product_platforms  products  questions  referral_links  request_upvotes
    review_contracts  review_requests  review_versions  review_votes
    reviews  user_badges  users

Including `users.email`, `users.password_hash`, `users.payout_account`,
`reviews.receipt_key` and `reviews.affiliate_link`.

**Not exposed** (no SELECT policy, so RLS denies by default): `sessions`,
`email_otps`, `payouts`, `commissions`, `moderation_logs`, `token_transactions`,
`review_comments`, `review_comment_votes`, `affiliate_postbacks`,
`honesty_fund_distributions`, `alembic_version`. Session records and OTP codes —
the two that would turn a read into an account takeover — were never reachable.

**Writes were not possible.** Every INSERT/UPDATE/DELETE policy tests
`= auth.uid()`, which is NULL for an anonymous caller, so RLS refused them. The
grant itself was `arwdDxtm` (ALL), and TRUNCATE is the one verb RLS does not
filter — but PostgREST cannot emit one, so it stayed latent. `0029` removes the
grant regardless.

### Apply

```bash
cd backend && alembic -x allow_production=1 upgrade head     # 0027, 0028, 0029
```

Or, faster, in the Supabase SQL editor:

```sql
REVOKE ALL   ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL   ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL   ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
```

The default-privileges line matters as much as the others: Supabase re-grants
every newly created table to `anon`, so without it the next migration that adds
a table reopens this silently.

### Verify — anonymous must be refused

```bash
KEY=<publishable key from the Supabase dashboard>
for t in users reviews review_versions products questions; do
  curl -s -o /dev/null -w "%{http_code} $t\n" \
    -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
    "https://byobedbhodhvocgrkrse.supabase.co/rest/v1/$t?select=id&limit=1"
done
```

**Pass:** every line `401` or `403`. A `200` with `[]` is **not** a pass — that
means the query still ran and simply matched nothing. Ask for `select=id` only;
there is no reason to pull a row to prove a door is shut.

### Verify — the application is unaffected

It should be entirely unaffected: the API connects as `postgres` via SQLAlchemy,
storage uses the service-role key, and `get_publishable_client()` is never
called. Confirm anyway, because this is a privilege change.

```bash
for u in / /search /categories /compare /questions /requests /membership \
         /api/v1/reviews/feed?limit=6 /api/v1/products?limit=5 \
         /api/v1/questions /api/v1/requests /api/v1/membership-tiers; do
  curl -s -o /dev/null -w "%{http_code} $u\n" "https://www.bluntly.ph$u"
done
```

**Pass:** all `200`. Then storage separately — public product images and review
photos still load, the private receipt bucket still refuses anonymous reads, and
a moderator can still open a receipt through `GET /api/v1/reviews/{id}/receipt`
(signed, 300s TTL).

---

## F. Production configuration

**Found by audit on 2026-08-20, and the only finding here that is live in
production right now.**

Fourteen consecutive failed logins from one address returned 401 and never 429,
against a configured limit of ten per minute. Login, register, OTP request, OTP
verify, voting, reporting and commenting are all unthrottled.

Two settings are involved, and both are absent from the repository:

| Variable | Effect of it being unset |
|---|---|
| `REDIS_URL` | ~~The limiter reaches for `localhost`, fails, and allows.~~ **Resolved 2026-08-21**: migration `0028` is applied and the Postgres fallback is verified enforcing — ten failed logins answer `401`, the eleventh answers `429`. Redis remains unconfigured; it is now a warning, not a refusal, so it no longer blocks `APP_ENV`. Configure it to restore the faster path. |
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

### Readiness table

`main.py` refuses to boot when `production_issues()` returns anything — but it
only consults that list when `APP_ENV` is exactly `production`. The app is
running, so **none of these checks are running**.

Several of them test the configured *string*, not observable behaviour, so
external probing cannot fully predict the result. Where a row says "needs
dashboard", that is why — not an oversight.

| Check | Verified from outside? | Would `APP_ENV=production` pass? | Owner action | Security consequence of it failing |
|---|---|---|---|---|
| `JWT_SECRET` ≥ 32 chars | Partly — tokens issue and verify, so it is set; length unknowable | Likely | Confirm length | Forgeable sessions |
| `USE_SUPABASE` + connection string | **Yes** — production serves database-backed pages | **Pass** | None | No database |
| `DATABASE_URL` not localhost | n/a — `USE_SUPABASE=true` | **Pass** | None | — |
| `CORS_ORIGINS` has no `*` | **Yes** — no preflight reflects an origin, no wildcard | Likely | Confirm string | Any site reads authenticated responses |
| `CORS_ORIGINS` not localhost | Behaviour safe; string unknown | Needs dashboard | Confirm string | Production browser origin refused |
| `REDIS_URL` not localhost | ~~14 failed logins, no 429~~ **Resolved 2026-08-21** | **Warning, not a refusal** | Optional — configure Redis for the fast path | Was: brute-force protection absent. `0028` applied and verified enforcing |
| `PII_HASH_SALT` not placeholder | Partly — the retention sweep hashes successfully, so one is set; whether it is the placeholder is unknowable | Needs dashboard | Confirm set | Hashed identifiers become guessable |
| Runtime uses the **transaction** pooler (:6543) | **Yes** — `runtime_database_url` resolves to `…pooler.supabase.com:6543` | **Pass** | None | Session pooler caps at ~4 clients; API 500s under load |
| `THREADPOOL_TOKENS` ≤ DB pool capacity | **Yes** — 20 ≤ 20 (`DB_POOL_SIZE` 10 + `DB_MAX_OVERFLOW` 10) | **Pass** (exactly at the limit) | None | Surplus queues on the pool and 500s after `DB_POOL_TIMEOUT` |
| `PAYOUT_PROVIDER=paypal_live` creds | n/a — provider is not live (FR-6 blocked on sandbox creds) | **Pass** | None | — |
| `PAYPAL_BASE_URL` not sandbox when live | n/a — same | **Pass** | None | — |
| `LAZADA_POSTBACK_SECRET` ≥ 32 | Partly — the endpoint answers 403 anonymously, so something is enforced | Needs dashboard | Confirm length | Anyone guessing the path fabricates conversions |
| `EMAIL_PROVIDER` not console | **Yes** — Resend delivers (202 to real domains) | **Pass** | None | Every OTP silently fails; codes land in logs |
| `RESEND_API_KEY` set | **Yes** — same evidence | **Pass** | None | OTP delivery fails |

### Answered 2026-08-21 — zero refusals. `APP_ENV` is the only thing left.

**The earlier prediction on this page was wrong and is corrected here.** It said
`CORS_ORIGINS` was the one refusal standing in the way. That came from
evaluating the *repository's* `.env`, which simply does not set `CORS_ORIGINS`
and so falls back to a localhost default. Vercel sets it correctly. Nothing was
wrong with production; the measurement was wrong.

Ground truth, read out of the running production process:

```json
{"message": "production readiness", "app_env": "staging",
 "is_production": false, "would_boot_as_production": true,
 "refusal_count": 0, "refusals": [],
 "warnings": ["REDIS_URL points at localhost ..."]}
```

`APP_ENV` is **`staging`**, which is why none of the production checks are
running. Set it to `production` and the app boots with every check on:

```bash
vercel env update APP_ENV production --value production --sensitive --yes
vercel --prod          # environment changes need a redeploy to take effect
```

### Why the checker cannot answer this from outside

Every environment variable on the Vercel project is marked **sensitive**, and
sensitive variables are write-only. Neither CLI path returns a real value:

| Path | What it actually returns |
|---|---|
| `vercel env pull` | the literal string `[SENSITIVE]` |
| `vercel env run` | empty strings |
| `vercel env ls` | `Hidden`, with the type column reading `Sensitive` |

So `check_production_config --env-file` run against a pulled file describes a
configuration that does not exist. It reported three phantom refusals here —
`USE_SUPABASE`, `OTP_TTL_SECONDS`, `OTP_MAX_ATTEMPTS` — none of which is
actually unset. **Do not trust a local run against pulled production values.**
The flag remains useful for any project whose variables are not sensitive.

The real values exist in exactly one place, so that is where the question is
answered: `main.py` evaluates `production_issues()` on every boot regardless of
`APP_ENV` and logs the result. Descriptions only, never values.

```bash
curl -s -o /dev/null "https://www.bluntly.ph/api/v1/reviews/feed?limit=1"   # force a cold start
vercel logs <deployment-url> --json | grep "production readiness"
```

### Safe sequence

Ordered so that no step can take production down:

1. **Configure** every value the table marks as needing the dashboard.
2. **Verify without changing `APP_ENV`** — `check_production_config` must print
   `READY`. This is the whole point of the script: the check runs, the flag
   does not move, and nothing can fail to boot.
3. **Apply `0028`** if `REDIS_URL` is to stay unset — the Postgres fallback is
   inert until its table exists.
4. **Set `APP_ENV=production`** and deploy.
5. **Verify boot** — `curl -s -o /dev/null -w "%{http_code}" https://www.bluntly.ph/api/v1/reviews/feed?limit=1`
   must be `200`. A failure to boot shows as a 500 from every route, and the
   fix is to unset `APP_ENV` and re-run step 2.
6. **Verify the controls are now on** — twelve failed logins for a nonexistent
   account from one address must produce a `429`:
   ```bash
   for i in $(seq 1 12); do
     curl -s -o /dev/null -w "%{http_code} " -X POST \
       -d "username=probe-$RANDOM@example.invalid&password=x" \
       https://www.bluntly.ph/api/v1/auth/login
   done; echo
   ```
   **Pass:** at least one `429` in the last two. All `401` means the limiter is
   still open — check that `0028` is applied and `rate_limit_counters` exists.

---

## F2. Page weight — owner action, measured

At a 393px viewport the homepage fetches **6 images totalling 1299 KB**, which
is 96% of the page's 1359 KB. The audience is Filipino mobile shoppers, so this
is the number that matters most on the first screen they see.

`loading="lazy"` is now on the feed, list and comparison images. Measured
before and after against production: **no change**, on any page. With six
published reviews every image sits inside Chrome's lazy threshold, so nothing
is deferred. It is correct and it will matter as the catalogue grows; it does
nothing today, and the runbook should not pretend otherwise.

The lever that works now is the source images. `seed_product_images.py`
downscales to an 800px longest edge and re-encodes an opaque PNG as JPEG.
Measured across the five images already in storage:

| | before | after |
|---|---|---|
| Anker power bank | 887 KB | 172 KB |
| CeraVe cleanser | 165 KB | 69 KB |
| Jisulife fan | 120 KB | 45 KB |
| MacBook Air | 98 KB | 98 KB (already optimal) |
| Akko keyboard | 35 KB | 35 KB (already optimal) |
| **total** | **1305 KB** | **419 KB — 68% smaller** |

```bash
cd backend && python -m scripts.seed_product_images --from-file
```

Writes to Supabase Storage, so it is an owner action. Re-run it and the
homepage drops to roughly 420 KB of images with no visible difference at the
size they display.

The remaining option, if that is not enough, is `next/image` with
`remotePatterns` for the Supabase host — automatic resizing and modern formats
per request. Not done here: it changes how every image is served, needs a CSP
review, and is a larger change than a release-hardening pass should make.

---

## F3. Scheduled work has no scheduler — owner action

`celery_app.beat_schedule` defines four periodic jobs. **None of them run.**
`docs/PRODUCTION.md` documents a deployment of app + Celery worker + beat, but
`vercel.json` declares two services — `frontend` and `backend` — and no worker,
and the broker points at the same unconfigured Redis that left auth rate
limiting open.

| Job | Schedule | Runs? | Manual trigger |
|---|---|---|---|
| Honesty Fund distribution | 1st, 02:00 Manila | no | **yes** — `POST /api/v1/admin/honesty-fund/run` |
| Payout scheduling | daily | no | **yes** — `POST /api/v1/admin/payouts/run` |
| PII retention sweep | 03:00 daily | no | **yes** — `POST /api/v1/admin/pii-retention/run` (added here) |
| Wilson re-rank | 04:00 daily | no | none |
| Trust progression | 04:30 daily | no | none |

Celery's timezone *is* correctly `Asia/Manila` with `enable_utc=True`, so the
schedule itself is right. There is simply nothing running it.

### ✅ PII retention — run 2026-08-21

Run through the authorized moderator path against production. Before: 226
sessions, 30 holding a raw IP, **3 past their 30-day deadline**. The sweep
returned `{"hashed": 3, "purged": 0}`. After: raw IPs 30 → 27, hashed 12 → 15,
overdue **3 → 0**, session count unchanged at 226 and user agents untouched —
exactly three rows changed, and only the overdue ones. A second run returned
`{"hashed": 0, "purged": 0}`, confirming idempotency.

The temporary QA moderator used for it was removed afterwards: users back to
14, zero QA markers, zero orphaned reviews or sessions.

Until a scheduler exists, this is the maintenance procedure — run it monthly,
or whenever `check_invariants` reports sessions past their deadline.

### The original finding

Measured 2026-08-21: **225 sessions, 29 holding a raw IP, three already past
their 30-day hashing deadline.** The 90-day deletions begin falling due from
late October. The retention schedule is a promise about people's data, so it
should not be waiting on a process nobody deployed:

```bash
curl -X POST -H "Authorization: Bearer <moderator token>"   https://www.bluntly.ph/api/v1/admin/pii-retention/run
```

Idempotent — the sweep selects on deadlines, so a second run finds nothing.

### The two with no trigger

Wilson re-rank and trust progression have neither a worker nor an endpoint.
Neither is silently broken: `wilson_score` is recomputed on every vote and
`recompute_user_trust` runs on publish, so both stay roughly current through
ordinary activity. What never happens is the **time decay** — the "time-decayed
Wilson Score ranking" the PRD names as core — re-applying to reviews that are
not being voted on. Ranking drifts stale rather than wrong.

### Fixing it properly

Vercel supports scheduled functions via a `crons` block in `vercel.json`
hitting an endpoint on a schedule. That is the platform-native answer and needs
no worker. It is not done here because it changes deployment configuration and
the cron endpoints need their own authentication — an owner decision, not a
hardening edit.

---

## F4. Data repair — reviews stranded by the old `unpublish` — ✅ DONE

**Applied 2026-08-21. One record. Owner-authorised.**

Until `b7a506a`, `unpublish` cleared `published_at` and left
`earn_eligible_status` alone. `get_queue` selects `pending` AND unpublished, so
a review taken down left the site *and* the moderation queue in the same
moment: no moderator control could reach it again, and the only way back was
knowing the UUID. Both reviews found in that state got there by a moderator
using a documented control correctly.

The code fix stops new ones. It does not move records already stranded, so
those were repaired by hand.

| | |
|---|---|
| Review | `10856799-62bf-445b-a035-a26e885af9a2` — "Moderation loop probe" |
| Author | a real account (not a QA identity) |
| Before | `approved`, `published_at IS NULL`, `is_removed = false`, unpublished 2026-08-10 |
| After | `pending` — everything else byte-identical |
| Stranded for | 11 days |

The second stranded review was a QA record from this sprint's own moderator
phase and was removed with the rest of that run's data, not repaired.

```sql
-- Every precondition is in the WHERE clause, so this can only match that one
-- record in that one state. Re-running it after the fact changes nothing.
UPDATE reviews
SET earn_eligible_status = 'pending'
WHERE id = '10856799-62bf-445b-a035-a26e885af9a2'
  AND published_at IS NULL
  AND is_removed = false
  AND earn_eligible_status = 'approved';
```

Deliberately **not** touched: `published_at` stays NULL (the repair does not
publish anything), `is_removed` stays false, `verification_status` stays
`unverified` — proof-of-purchase evidence is never rewritten to make a record
tidy — and title, body, author and `current_version` are untouched.
`updated_at` did not drift either: no trigger fired, so the record still
carries its real last-edited time rather than the time an engineer touched it.

Verified afterwards through the moderator API, not just in SQL: the review
appears in `GET /admin/review-queue` among 9 pending items, `published_at`
null, status `pending`. The QA moderator account created to run that check was
deleted immediately after.

**Standing check.** This query must stay at zero. Anything it returns is
unreachable by moderators and invisible to readers:

```sql
SELECT count(*) FROM reviews
WHERE is_removed = false AND published_at IS NULL
  AND earn_eligible_status NOT IN ('pending', 'rejected');
```

---

## G. Security incident response — password-hash exposure

`users.password_hash` was readable. The values are Argon2id, so they are not
passwords, but they are authentication material and suitable for offline attack.
The decision below is the owner's; this section gathers the evidence needed to
make it.

**Do not run a mass password reset unless the decision is made deliberately.**
The repository has no forced-reset state today, so "reset everyone" is not a
one-command operation and would lock real users out of accounts they can still
reach safely.

| Level | Action | When it is the right call |
|---|---|---|
| **1 — Containment only** | Apply E, monitor. | No evidence of access beyond the audit itself, and the affected population is small and known. |
| **2 — Containment + notification** | Tell affected users what was exposed, without claiming password compromise. | Any real user's email, payout account or review identity was reachable. |
| **3 — Containment + forced reset** | Invalidate sessions and require new passwords. | Evidence of actual third-party reads, or a population large enough that offline attack is worth someone's time. |

### Evidence to gather before choosing

- **How long was it open?** The permissive policies date from the RLS migration
  that created `users_select_public`. `git log` that file; treat its merge date
  as the start of exposure.
- **How many real accounts?** Production holds a small number of real users
  after the fixture cleanup. Count non-fixture rows before deciding — the
  cleanup manifest distinguishes them.
- **Was it actually read?** Supabase logs REST requests. Look for `/rest/v1/*`
  entries that are not this audit, separated by user agent and timestamp. The
  application's own traffic never appears there, because it does not use
  PostgREST — so *any* REST entry is worth reading closely.
- **Session invalidation — there is no lever.** Identity is a stateless JWT
  with a 24-hour expiry (`access_token_expire_minutes`), and the API has no
  logout or revocation endpoint: `logout()` clears the httpOnly cookie in the
  browser and nothing else. A token already issued stays valid for up to 24
  hours whatever happens to the password.

  The `sessions` table is **not** auth sessions — it is affiliate click
  tracking with a PII retention schedule. Do not reach for it expecting
  revocation.

  This is what makes level 3 awkward rather than merely disruptive: a forced
  reset would not evict anyone holding a current token, so it buys less than it
  appears to while costing every real user their access. If revocation is
  wanted, it is a piece of work to plan, not a step in an incident.
- **Payout accounts** were exposed and are a separate notification question from
  passwords.

### Evidence gathered 2026-08-20

**Access logs — checked.** Supabase logs every PostgREST request with path,
method, status and user agent (`edge_logs`). Querying the full available window
for `/rest/v1/*`:

> **Every request was the audit's own.** All 17 entries carry the user agent
> `rt/1`, which is the one this audit set. Nothing else appears.

This is unusually clean evidence because **the application produces no
PostgREST traffic at all** — it connects as `postgres` via SQLAlchemy and uses
the service-role key for storage. So the baseline is zero, and any entry is
anomalous by definition. There is no need to separate application noise from
third-party access; there is no application noise.

**The caveat that matters:** the log window is capped at 24 hours, and the
exposure predates that by however long the permissive policies have existed.
This shows no third-party access *recently*. It cannot show none *ever*. If
longer retention is available on the plan, widen the window before deciding —
that is the single piece of evidence that would move this between levels.

**Supabase's own advisor would not have caught this.** `get_advisors(security)`
flags the 11 tables that have RLS enabled and *no* policy — the safe ones —
as INFO, and says nothing about the 17 returning `password_hash` and `email`,
because from its perspective a table with a policy is a table that is handled.
Worth knowing before relying on it as a control.

### Recommendation on this evidence

**Level 2 — containment plus notification.** Level 1 understates it: real
users' email addresses and payout accounts were reachable by anyone with a key
Supabase gives out freely, for an unknown but not-short period, and that is
worth telling people about regardless of whether anyone looked.

Level 3 is not indicated. There is no evidence of a third-party read, the
hashes are Argon2id, `sessions` and `email_otps` were never exposed so no
session material leaked, and the repository has neither a forced-reset
mechanism nor token revocation — so executing it would mean building both under
incident pressure, locking real users out of accounts that are not known to be
compromised, and still leaving every already-issued token valid for 24 hours.

Revisit if wider log retention shows REST traffic that is not `rt/1`.

### Owner decision to record

> Whether to notify users, and at which level. Level 2 is the conventional
> floor once real users' email and payout details were reachable, even absent
> evidence of a third-party read. Level 3 is not indicated on current evidence
> and is not supported by a safe mechanism in the codebase today.

---

## H. Final release verification

The order matters: containment first, then configuration, then the suites that
need them, then the verdict.

| # | Step | Command | Pass looks like |
|---|---|---|---|
| 1 | Apply pending migrations | `cd backend && alembic -x allow_production=1 upgrade head` | production at `0030` |
| 2 | Verify PostgREST sealed | §E "Verify — anonymous must be refused" | every table `401`/`403` |
| 3 | Verify the app is unaffected | §E "Verify — the application is unaffected" | all `200` |
| 4 | Validate production config | `python -m scripts.check_production_config` | `READY` |
| 5 | Set `APP_ENV=production`, deploy | §F "Safe sequence" | boots, serves `200` |
| 6 | Verify rate limiting | §F step 6 — twelve failed logins | at least one `429` |
| 7 | Run the isolated DB suite | `python -m scripts.bootstrap_test_env` | ~669 passed, **0 skipped** |
| 8 | Run the milestone verifier | `python -m scripts.verify_milestones` (Git Bash) | `58/58 verified` |
| 9 | Run Ruff | `cd backend && python -m ruff check app/ scripts/ tests/` | `All checks passed!` |
| 10 | Frontend verification | `npx tsc --noEmit && npm run lint && npm run build` | clean, every route emitted |
| 11 | Data integrity | `python -m scripts.check_invariants --strict` | `All 15 invariants hold` |
| 12 | Production smoke | steps 3b and 5–6 below | as stated there |
| 13 | PayPal sandbox acceptance | §C, scenarios 1–8 | no double debit or refund |
| 14 | Security matrix | step 6 below | every row holds |
| 15 | **Verdict** | §"Contractual verdict" below | every FR resolved |

Steps 1–6 are the ones currently outstanding. 7 and 8 are blocked on §A.
13 is blocked on §C.

### The commands in full

```bash
# 7. Backend, with the isolated DB — expect 0 skips
cd backend && .venv/Scripts/python -m scripts.bootstrap_test_env

# 9. Static analysis. Not optional: with the DB-backed half of the suite
#    unavailable it is most of what stands between an edit and production, and
#    a NameError in create_review reached production exactly that way.
cd backend && .venv/Scripts/python -m ruff check app/ scripts/ tests/

# 10. Frontend
npx tsc --noEmit && npm run lint && npm run build

# 11. Data integrity — read-only, safe against production
cd backend && .venv/Scripts/python -m scripts.check_invariants --strict

# 3. Browsers — SERIALLY. Five engines in parallel exhausted this host once and
#    produced 180 spurious failures; serial runs are just as valid.
for p in chromium firefox webkit mobile-chrome mobile-safari; do
  npx playwright test --project=$p --workers=1
  npm run dev:stop
done
```

**3b. Browsers against production** — the read-only specs can be pointed at a
deployed origin, which is the only way to check that what is *deployed* renders.
It also works when there is no local database, where the local stack renders
empty states and the suite tests nothing:

```bash
PLAYWRIGHT_BASE_URL=https://www.bluntly.ph npx playwright test   e2e/console-health.spec.ts e2e/accessibility.spec.ts   --project=chromium --workers=1
PLAYWRIGHT_BASE_URL=https://www.bluntly.ph npx playwright test   e2e/responsive.spec.ts --project=mobile-chrome --workers=1
```

**Pass:** 27 tests. Zero console errors, real content, styles applied, no
horizontal scroll at 393px.

**Write specs are excluded automatically.** `playwright.config.ts` drops
`route-guards.spec.ts` whenever `PLAYWRIGHT_BASE_URL` is not localhost — it
submits forms, and production is not a fixture. Enforced in the config rather
than left to whoever types the command, because a stray account is silent and
permanent.

**Chromium engines only.** Vercel's bot protection challenges Playwright's
headless WebKit: every request returns **403** with a body linking to
`vercel.link/security-checkpoint`. It is reputation-based, so it appears after
a run or two of sustained traffic and then applies to every path — a run that
passed an hour ago will fail wholesale.

A 403 carrying `security-checkpoint` means the checkpoint, **not a broken
site**. Verified: ordinary clients, including ones sending a Safari user agent,
get 200 throughout. Real Safari users are unaffected; it is the headless
fingerprint being challenged.

Do not attempt to defeat it. Run production smoke on `chromium` and
`mobile-chrome`, keep the volume low, and run `firefox`, `webkit` and
`mobile-safari` against the local stack where the full matrix belongs anyway.

# 4. Migration safety, before any further schema change
cd backend && .venv/Scripts/python -m scripts.check_migration_safety --all
```

**4b. Data integrity** — read-only, and the one check that is safe to point at
production, because production is the only place the data is real:

```bash
cd backend && python -m scripts.check_invariants --strict
```

Thirteen invariants the code states in prose and then relies on: the wallet
identity, no orphaned reviews or payouts, no review with two active referral
links, no monetized-but-unverified review, no monetized review at two stars or
below, commission shares summing to the gross, and none of them negative.

**Pass:** `All 15 invariants hold.`

**Two currently fail, and they are known residue.** The fixture cleanup deleted
the synthetic users and reviews but left 132 rows in
`honesty_fund_distributions` behind — recording ₱73,149.89 of Honesty Fund
payments, attributed to nobody, dated `1970-01-01`. Nothing is corrupt: the
foreign keys are `ON DELETE SET NULL` and did exactly that. It is money-shaped
fiction sitting in a money table, and any report of "total distributed" would
include it.

```sql
-- Both conditions together. A real distribution has a reviewer and a real
-- cycle month, so this cannot reach one.
DELETE FROM honesty_fund_distributions
 WHERE reviewer_id IS NULL AND cycle_month < DATE '2020-01-01';
```

Expect `DELETE 132`, after which `check_invariants` reports all 15 holding. A failure names the invariant and says what
a non-zero count means, so the output is the diagnosis.

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
