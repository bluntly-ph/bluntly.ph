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

## E. PostgREST containment — DO THIS FIRST

**Status: live exposure until the migration is applied.** Found 2026-08-20.

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
| `REDIS_URL` not localhost | **Yes — FAILS.** 14 failed logins, no 429 | **FAIL** | **Set `REDIS_URL`, or apply `0028`** | **Auth brute-force protection absent — live now** |
| `PII_HASH_SALT` not placeholder | No | Needs dashboard | Confirm set | Hashed identifiers become guessable |
| `PAYOUT_PROVIDER=paypal_live` creds | n/a — provider is not live (FR-6 blocked on sandbox creds) | **Pass** | None | — |
| `PAYPAL_BASE_URL` not sandbox when live | n/a — same | **Pass** | None | — |
| `LAZADA_POSTBACK_SECRET` ≥ 32 | Partly — the endpoint answers 403 anonymously, so something is enforced | Needs dashboard | Confirm length | Anyone guessing the path fabricates conversions |
| `EMAIL_PROVIDER` not console | **Yes** — Resend delivers (202 to real domains) | **Pass** | None | Every OTP silently fails; codes land in logs |
| `RESEND_API_KEY` set | **Yes** — same evidence | **Pass** | None | OTP delivery fails |

**One proven failure, several unknowable from outside.** Do not set
`APP_ENV=production` before resolving them: the app would raise at import and
the deployment would stop serving.

### Answer it without guessing

```bash
cd backend && python -m scripts.check_production_config
```

Run it where the production values live — a Vercel shell, or locally with the
production environment exported. It evaluates the same `production_issues()`
list that `main.py` uses and prints **descriptions only, never values**, so the
output is safe to paste into a ticket. `--strict` exits non-zero when the app
would refuse to boot, which makes it usable as a deploy gate.

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

**Only the read-only specs.** `route-guards.spec.ts` submits forms, and
production is not a fixture.

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
