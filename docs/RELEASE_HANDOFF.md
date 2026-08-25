# Release handoff — engineering → QA

**Prepared 2026-08-21; revised the same day after GitHub and Vercel were
re-authorised; extended 2026-08-26 for a second post-freeze sprint (see
"Owner-approved changes after the freeze (2026-08-26)").** Covers the full-stack engagement (frontend + backend
agreements) against the capstone PRD as amended by `docs/DEVIATIONS.md` and the
owner's scope decisions.

Two claims in the first revision were wrong and are corrected in place: CI was
not permanently blocked, and `CORS_ORIGINS` was not a production refusal. Both
corrections are marked where they appear.

## How to read this

`CURRENT ALIGNED REQUIREMENT` is what the obligation actually is today, not what
the original PRD said, where the owner has since amended it. Where the two
differ the deviation is cited — an amended requirement is not a shortfall.

Engineering statuses mean exactly one thing each:

| Status | Meaning |
|---|---|
| `ENGINEERING COMPLETE` | Built, deployed, and evidenced in production. No known defect. |
| `READY FOR QA RETEST` | A defect was found and fixed this sprint; the fix is live and regression-protected. QA has not independently retested it. |
| `BLOCKED EXTERNAL` | Cannot proceed without a third party. |
| `OWNER DECISION REQUIRED` | Cannot proceed without an owner action or ruling. |

**QA status is never asserted by engineering.** Every row says
`AWAITING INDEPENDENT QA` unless the QA team has recorded otherwise. A fix being
verified in production by engineering is evidence for retest, not a substitute
for it.

---

## Functional requirements

### FR-1 — Account & profile management

| | |
|---|---|
| **Current aligned requirement** | Email registration + login, profile management, RBAC at the API level, roles user/seller/moderator. **Forgot-password is descoped** — auth is email-OTP, so there is no password to recover (owner, 2026-08-07). |
| **Implementation** | App-native auth (ADR-010/011): Argon2id, HS256 JWT, 24h expiry, httpOnly cookie + BFF proxy. `require_role` dependency enforces RBAC per route. |
| **Production evidence** | RBAC sweep **18/18**: every `/admin/*` route answers `401` anonymous and `403` to an authenticated non-moderator, including the money endpoints. Registration, login and session round-trip verified. Auth endpoints rate-limited (see NFR-security). |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` |

There is no `admin` role: `MemberRole` is user/seller/moderator, and `moderator`
*is* the administrative role. The `/admin/*` prefix is a URL convention, not a
fourth role. Verified — not an omission.

### FR-2 — Product discovery & consolidation

| | |
|---|---|
| **Current aligned requirement** | Keyword search with filters/sort, category browsing, public browsing without an account, price panel at **≥3 independent** observations, comparison tool. Automated name standardisation explicitly out of scope (marketplace ToS). |
| **Implementation** | `/search`, `/categories`, `/compare`. Price panel independence rule extracted to `price_service.panel_from()` so it is unit-testable without a database. 14-slug canonical category vocabulary with read-side alias tolerance. |
| **Production evidence** | All discovery routes `200` across 5 browser engines. 14 category slugs link correctly and every filtered target resolves. Migration `0027` relabelled 6 products `electronics` → `electronics-tech`; category drift is guarded by tests. |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` |

### FR-3 — Review submission

| | |
|---|---|
| **Current aligned requirement** | Structured format (discussion, verdict, target/anti-target audience, 1–5 stars, pros/cons, title, photo). **Publication gate SUPERSEDES "publish immediately"** (deviation #30): a new review is hidden and auto-queued; a moderator publishes it. Photo at submission ⇒ *verified*. |
| **Implementation** | `create_review` sets `published_at = NULL`, `earn_eligible_status = pending`. `_verification_for()` grants *verified* only when the photo is a `review-photos` object **owned by the author** — a photo URL alone is not proof. |
| **Production evidence** | Live QA: a submitted review came back `published_at = null` and `verification_status = unverified` without an owned proof photo, then published only on moderator action. Both halves of the gate confirmed against production. |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` |

### FR-4 — Seller reviews & seller accounts

| | |
|---|---|
| **Current aligned requirement** | **Descoped by the owner** (2026-08-07, reaffirming the 2026-07-28 removal): bluntly.ph is an affiliate-review platform, not a merchant directory. The seller-facing frontend was removed; `0024_drop_seller_reviews` dropped the schema. |
| **Implementation** | Deliberately absent. Figma still contains `Seller Review — Step 1…3`, `Seller Page`, and `Mobile Search Page for Sellers` frames; these are **not** contractual and must not be read as missing screens. |
| **Production evidence** | n/a |
| **QA status** | OUT OF SCOPE — do not raise as a defect |
| **Engineering status** | `ENGINEERING COMPLETE` (by descope) |

### FR-5 — Community Q&A

| | |
|---|---|
| **Current aligned requirement** | Questions directed to buyers or seller; one Best Answer per question updating responder trust; First Responder badge within 24h; answers ranked by time-decayed Wilson. |
| **Implementation** | `/questions`, `/questions/[id]`, `/questions/new`. `qa_service` refuses self-dealing: a responder cannot be First Responder on their own question, and `mark_best_answer` raises `cannot_pick_own_answer`. |
| **Production evidence** | Q&A routes render and resolve; question creation verified in the authenticated QA phase. Self-dealing guards covered by `test_qa_self_dealing.py`. |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` |

**Known unresolved ambiguity (PRD's own):** "routes to registered users with
relevant product experience" — who counts as relevant, and how they are
notified, is unspecified in the source document. Not an engineering gap;
needs a product ruling before it can be built or tested.

### FR-6 — Incentives, earn_eligible & payouts

| | |
|---|---|
| **Current aligned requirement** | 40/30/30 split as the **baseline**, tiered via `revenue_share_bps` (3000/3500/4000) per ADR-012. Honesty Fund fixed at 30%. PayPal only, ₱300 minimum. **Payouts are scheduler-driven, never user-requested.** Membership tiers are status levels, not subscriptions — no checkout, no billing. |
| **Implementation** | `payout_service` sweeps everyone at/above the minimum with a payout account, in tier-priority order. Every guarded state transition takes a row lock (`SELECT … FOR UPDATE`) before deciding. Wallet mutations go through a single atomic `UPDATE`. Migration `0030` adds CHECK constraints so a tier cannot be saved at a share the split rejects. |
| **Production evidence** | Tier bound constraints present in production (`ck_tier_share_bps_range`, `ck_tier_payout_priority`). Money invariants hold: splits sum to gross, no negative shares, no negative wallet balances, no commission pointing at a missing review. |
| **QA status** | AWAITING INDEPENDENT QA (payout execution not testable — see below) |
| **Engineering status** | `BLOCKED EXTERNAL` for payout execution only; the surrounding logic is `ENGINEERING COMPLETE` |

`PAYPAL_SANDBOX = BLOCKED_EXTERNAL_ZIENT`. No sandbox credentials exist in the
authorised environment, so no payout has been executed end-to-end. **Live PayPal
will not be used for testing under any circumstance.** The acceptance sequence is
written and waiting in `RELEASE_ACCEPTANCE.md §C`; it runs automatically once
credentials appear.

### FR-7 — Trust progression

| | |
|---|---|
| **Current aligned requirement** | Six stages (0–5) with escalating privileges and gate-vote weights; accounts <30 days at half weight; probation zeroes gate-vote weight. Visibility votes stay equal-weight for everyone. |
| **Implementation** | `recompute_user_trust` triggered by publish/unpublish/reject, vote writes, and a nightly sweep. No manual stage-set endpoint by design. Badges award on the way up and are not removed on a drop (deviation #36). |
| **Production evidence** | Trust recomputation fires on the publish/unpublish transitions exercised in the moderator QA phase. Trust boundary behaviour covered by `test_trust_boundaries.py`. |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` |

**Known unresolved ambiguity (PRD's own):** `reputation_score` (0–100) has no
defined formula in the source document, and Stage 4's "relaxed proof" and Stage
5's "highest earning multiplier" are unquantified. Implemented to a documented
interpretation; a product ruling would be needed to call it conformant.

### FR-8 — Fraud deterrence (seven layers)

| | |
|---|---|
| **Current aligned requirement** | Layered frictional deterrence. **Fraud signals are advisory-only** (deviation #39) — they surface to the moderator and never auto-block. |
| **Implementation** | Proof-photo ownership check (layer 1), pg_trgm duplicate content >0.85 (layer 2), IP-based multi-account signals (layer 4), time-decayed Wilson with velocity flags (layer 5), community reporting with escalation (layer 6), trust-weighted gate voting on effective n (layer 7). Collusion detection per ADR-004 (≥5 up-voters, >0.6 reciprocated). |
| **Production evidence** | The moderation queue card exposes a `signals` block per review, confirmed live. Layer 1 verified end-to-end: a review with an unowned photo URL is *unverified*, and only verified reviews can be monetized (invariant, holds). |
| **QA status** | AWAITING INDEPENDENT QA |
| **Engineering status** | `ENGINEERING COMPLETE` for layers 1, 2, 4, 5, 6, 7 |

**Layer 3 (reverse image search + metadata) is not implemented.** The PRD does
not name a provider, and it requires a third-party service that has never been
selected or procured. `OWNER DECISION REQUIRED` — this is a procurement choice,
not engineering work that was skipped.

### FR-9 — Moderation & administration

| | |
|---|---|
| **Current aligned requirement** | Moderation queue with signals; approve/reject with star-rating routing; commission CSV import (Shopee + Lazada); earnings breakdown; payout processing; monthly Honesty Fund distribution; filterable audit log. |
| **Implementation** | `/admin/review-queue`, publish / reject / unpublish / referral-link attach and revoke, `/admin/reports`, `/admin/commissions/import`, `/admin/honesty-fund/run`, `/admin/pii-retention/run`. Every action writes a `moderation_logs` row. |
| **Production evidence** | Moderator phase **9/9** against production: queue reachable and correctly shaped, publish sets `published_at` and routes to an earnings state, unpublish returns the review to the queue, reports queue reachable. RBAC verified on every route. |
| **QA status** | **READY FOR QA RETEST** — one defect found and fixed this sprint |
| **Engineering status** | `READY FOR QA RETEST` |

---

## Defects found and fixed this sprint

All three were found by engineering during production QA, not reported by the QA
team. Each is live and regression-protected.

| # | Defect | Severity | Fix | Regression guard | Status |
|---|---|---|---|---|---|
| 1 | **Unpublishing a review removed it from the moderation queue as well as the site.** `get_queue` selects `pending AND unpublished`; `unpublish` cleared `published_at` but left the status, so the review became unreachable by any moderator control. Two production reviews were in this state, one for 11 days. | High — silent loss of moderator control over content | `b7a506a` — unpublish returns the review to `pending` and records the previous status in the audit context | `test_unpublish_returns_the_review_to_the_queue`, plus **invariant #18** which must stay at zero, plus a check in the production harness | `READY FOR QA RETEST` |
| 2 | **The production guard cleared destructive work to run against production.** `require_non_production("DELETE every review")` returned normally, connected to the live database, while printing `target: test \| db host: localhost`. Cause: `Settings` resolves `env_file` against the cwd; the guard resolved it absolutely, so from the repo root it merged a `.env.test` that pydantic never read. | **Critical** — this is the control added after the 2026-08-19 incident in which the suite ran against production and created hundreds of fixture reviews | `ea21b47` — the guard mirrors pydantic's resolution, and an already-imported config's real connection outranks any reconstruction | 4 new tests including one that pins the guard's entries against `Settings.model_config` itself; the CI `guard` job asserts a simulated production target is refused | `READY FOR QA RETEST` |
| 3 | **Every made-up `/u/{id}` was a real, indexable page.** The route rendered "Reviewer not found" inline at HTTP 200 instead of calling `notFound()`, and Next injects `noindex` only for genuine 404s. `/reviews` and `/questions` carried the tag; `/u` did not. | Medium — unbounded indexable near-duplicate pages | `c9b52ff` — `notFound()` plus a segment-level `not-found.tsx` keeping the reviewer-specific wording | Verified live across all three dynamic routes: missing resources carry `noindex`, real ones do not | `READY FOR QA RETEST` |

Also fixed: the migration safety scanner reported a `TRUNCATE` finding against a
migration that destroys nothing — it was reading the word out of its own
explanatory comment (`eb7013a`). Advisory only, but the report is about to become
a CI gate and a scanner that cries wolf gets ignored.

### Data repair

One production record was repaired, owner-authorised: review
`10856799…` ("Moderation loop probe"), stranded by defect #1 for 11 days,
returned to `pending`. Content, author, publication state and verification
evidence untouched; `updated_at` did not drift. Verified afterwards through
`GET /admin/review-queue`, not only in SQL. Full record in
`RELEASE_ACCEPTANCE.md §F4`.

---

## Non-functional requirements

| Area | Status | Evidence |
|---|---|---|
| **Security — transport** | `ENGINEERING COMPLETE` | TLS enforced; production serves HTTPS only |
| **Security — RBAC** | `ENGINEERING COMPLETE` | 18/18 live RBAC checks |
| **Security — direct DB exposure** | `ENGINEERING COMPLETE` | Migration `0029` revoked all PostgREST grants. Production: **0** tables readable by `anon`, **0** by `authenticated` (was 28 each). Live probe: `users`, `reviews`, `sessions` all `401`. Two invariants guard it continuously |
| **Security — brute force** | `ENGINEERING COMPLETE` | 10 failed logins `401`, the 11th `429` with RFC 9457 `problem+json` and `retry_after_seconds`. Enforced by the **Postgres fallback** (migration `0028`) with Redis unconfigured — `rate_limit_counters` recorded exactly 11 |
| **Privacy — RA 10173 retention** | `ENGINEERING COMPLETE` | Sweep endpoint live. Before: 226 sessions, 30 raw IPs, 3 overdue. After: 0 overdue, user agents untouched, total unchanged. Second run returned `{hashed: 0, purged: 0}` — idempotent |
| **Privacy — data-subject rights** | `OWNER DECISION REQUIRED` | The PRD's own gap: no access/rectification/erasure/portability workflow, privacy notice, breach-notification procedure, DPO designation or NPC registration is specified. Legal/product scope, not engineering |
| **Accessibility** | `ENGINEERING COMPLETE` for what is specified | No WCAG level is contractually required (PRD gap). The suite nonetheless asserts a WCAG 2.5.8 AA 24px target floor and passes on all 5 engines |
| **Performance** | `OWNER DECISION REQUIRED` | No quantitative target exists to test against (PRD gap: no p95, throughput, concurrency or uptime SLO). Measured facts: homepage image payload reduced from 1299 KB; runtime is on the Supabase **transaction** pooler (:6543), not the 4-client session pooler |

---

## Automated verification — all fresh as of 2026-08-21

| Check | Result |
|---|---|
| Backend — ruff (`app/ scripts/ tests/`) | **PASS**, clean |
| Backend — pytest (local, no database) | **584 passed**, 133 skipped |
| Backend — pytest (CI, isolated database) | **717 passed, 0 failed, 0 skipped** |
| Backend — environment guard tests | **27 passed** |
| **GitHub Actions CI** | **fully green** — guard, backend, frontend **and the isolated-database job** |
| **Isolated DB suite** | **717 passed, 0 failed, 0 errors, 0 skipped** (50m against `bluntly-ph-test`) |
| **Milestone verifier** | **58/58 verified** — run against the isolated project, not from historical counts |
| Backend — migration safety | **PASS** (advisory; 10 migrations flagged for deliberate rollout order) |
| Production — data integrity invariants | **18/18 hold** |
| Frontend — TypeScript (`tsc --noEmit`) | **PASS** |
| Frontend — ESLint | **PASS** |
| Frontend — production build | **PASS** |
| Production e2e — Chromium | 40 passed, 0 failed |
| Production e2e — mobile Chromium (Pixel 7) | 40 passed, 0 failed |
| Production e2e — Firefox | 40 passed, 0 failed |
| Production e2e — WebKit | 40 passed, 0 failed |
| Production e2e — mobile Safari (iPhone 14) | 40 passed, 0 failed |
| Navigation audit | 31/31 linked targets resolve; **0 dead controls** across 18 pages; `?next=` preserved on every gated route |

**200 browser assertions, zero failures, no bot checkpoint encountered.**

### WebKit degradation on the development host — infrastructure, not the app

A second full smoke late in the session had both WebKit projects
(`webkit`, `mobile-safari`) run one test and then stall, reporting the rest as
"did not run". Classified as a **test-infrastructure limitation** on this
Windows machine, on this evidence:

- Both WebKit projects passed **40/40 each** earlier in the same session, on the
  same commit range, against the same deployment.
- Chromium re-run immediately afterwards passed **7/7** on the identical spec.
- Production serves that exact iPhone user agent a normal `200` with real
  server-rendered HTML — checked with `curl`. **No bot checkpoint**: no
  `security-checkpoint`, no `vercel.link`, no challenge markers.
- `playwright.config.ts` already documents WebKit dying on Windows
  (`STATUS_STACK_BUFFER_OVERRUN`) and taking unrelated tests down with it,
  which is why workers are capped at 2 on `win32`.

Nothing was bypassed or relaxed to make this green — the earlier passing run is
the evidence, and this note is the caveat on it. Re-running the WebKit projects
on a fresh host, or in CI on Linux, is the way to confirm independently.

The 6 skips per engine are `moderator-a11y`, which requires
`E2E_MODERATOR_TOKEN` and whose own header says never to point it at
production. That is a **test-infrastructure limitation**, not an application
failure — it needs the isolated test project, not a code change.

### The 133-skip gap — closed, and what it was hiding

Every `requires_db` test skips on the development machine: Docker/WSL cannot
start a local Postgres, and the suite is deliberately pinned away from Supabase
because that project **is** production. They now run in CI against the isolated
`bluntly-ph-test` project: **717 passed, 0 failed, 0 errors, 0 skipped**, plus
the milestone verifier at **58/58**.

It was never only a coverage statistic. The first run against a real database
found eleven problems, none of them production defects, and four of them tests
that had never been capable of passing:

| Found | What it was |
|---|---|
| 4 errors | `test_postgrest_surface` and `test_wallet_concurrency` take a `db` fixture, and one imports `make_user`. **Neither existed.** Skipped since the day they were written, so "fixture not found" was never reported — they counted as coverage while being incapable of running |
| 1 failure | `test_all_fifteen_tables_present` still demanded `seller_reviews`, dropped by `0024` when FR-4 was descoped |
| 1 failure | A price test computed "tomorrow" in UTC. The validator uses the **Philippine** date on purpose, so for eight hours a day UTC's tomorrow is Manila's today and is correctly accepted. The test was wrong; the product was right |
| 1 failure | The tier-cap test set `revenue_share_bps = 7001` to exercise an import guard — but `0030`, added so that state could not be stored, now rejects the write, and the test died in its own setup |
| 1 failure | My own doing: pinning `DB_POOL_SIZE=2` for CI leaked into a config test that reads ambient environment |
| 1 failure | A default-privileges assertion that **cannot hold on Supabase** and failed against production too — see below |
| 2 failures | Receipt-privacy tests: the test project had no storage buckets. All four now provisioned, matching production, `review-receipts` private |

**The one genuine limitation.** The test required that no role in `public` has a
default-ACL granting `anon`. `supabase_admin` carries one, and only that role or
a superuser may change it. Checked against both databases: `postgres` — the role
migrations actually run as — is clean in each, `supabase_admin` grants in each.
The assertion is now the true and narrower one: *a table created by our
migrations is not exposed*. The residual risk is a table created by Supabase's
own tooling, and the two `check_invariants` privilege checks fail the moment any
table becomes readable by `anon` or `authenticated` — detection rather than
prevention, which is the honest description of what is achievable here.

Getting there also required three fixes to the chain itself: a revision id one
character too long for `alembic_version` (33 vs `VARCHAR(32)`), a migration that
could not render offline, and `0029` failing outright on a permission Supabase
never grants. Each made a from-scratch database impossible, and each was
invisible from a database that had already migrated past it.

---

## Blocked — needs someone other than engineering

Four items on this list were resolved on 2026-08-21 once GitHub and Vercel were
re-authorised. What follows is only what genuinely remains.

| Item | Marker | Exact action required |
|---|---|---|

| **BUG-030 badge wording** | `OWNER / PRODUCT DECISION` | The UI says "Verified purchase"; the contract means "a photograph was attached", which is materially weaker. Options are documented in `BUG-030-verification-semantics.md`: soften the badge, or raise the bar to require a receipt. **Not changed unilaterally** — it is a public trust claim |
| **PayPal sandbox** | `PAYPAL_SANDBOX = BLOCKED_EXTERNAL_ZIENT` | Zient to provide sandbox credentials. The acceptance sequence runs automatically once they are in the authorised environment |
| **FR-8 layer 3** | `OWNER DECISION REQUIRED` | Select a reverse-image-search provider. The PRD names none. No paid service will be procured without approval — see the decision brief below |

### Resolved since the previous handoff

| Was | Now |
|---|---|
| `APP_ENV=staging`, production checks off | **`APP_ENV=production` — live and verified.** The running process reports `is_production: true`, `refusal_count: 0`. Rate limiting, PostgREST denial and the private receipt boundary all re-verified with the checks executing |
| `GITHUB_CI = BLOCKED_AUTH` | **Active and green.** `gh auth refresh -h github.com -s workflow` granted the scope; the workflow runs on every push and has already caught a real regression |
| Vercel connector unusable | **Usable.** The official CLI is authenticated and linked to the existing `bluntly-ph` project. The MCP still 404s on the project, but the CLI is the supported path |
| `CORS_ORIGINS` blocks `APP_ENV` | **False alarm, corrected.** That came from the repo's `.env`, which does not set it. Vercel sets it correctly. Real refusal count is **0** |
| `TEST_SUPABASE_URL` missing | **All three secrets set.** The isolated DB job runs on every push |
| **133 skipped DB tests** | **Closed.** `717 passed, 0 failed, 0 skipped` against the isolated project, plus milestone verification `58/58`. See below |

### FR-8 layer 3 — decision brief

```
Requirement          reverse image search + metadata analysis, surfaced to the moderator
Current provider     none — the PRD names none
Blocked by           provider selection and procurement, not engineering
Possible now         an adapter interface + stub, so the moderator card has a slot
                     to render into and swapping a provider in is a one-file change
Cost position        no paid service will be signed up for without explicit approval
```

The other six layers are implemented and advisory-only, which is the agreed
behaviour — signals surface to the moderator and never auto-block. Layer 3's
absence therefore degrades the *quantity* of signal on a card, not the
correctness of any decision.

### `APP_ENV=production` — ✅ LIVE. `PRODUCTION_CONFIG = COMPLETE`

**Correcting the previous handoff.** It named `CORS_ORIGINS` as the blocker.
That was measured against the repository's `.env`, which does not set
`CORS_ORIGINS` at all and so falls back to a localhost default. Vercel sets it
correctly. Production was never misconfigured — the measurement was.

Applied, then confirmed from the running process rather than the dashboard:

```json
{"message": "production readiness", "app_env": "production",
 "is_production": true, "would_boot_as_production": true,
 "refusal_count": 0, "refusals": [],
 "warnings": ["REDIS_URL points at localhost ..."]}
```

Redeployed with `vercel redeploy <url> --target production` rather than
`vercel --prod`, so the deployment rebuilt the exact same commit with the new
environment instead of uploading whatever sat in a local working tree.

Post-flip, with every production check now actually executing: all public
routes `200`; rate limiting still 10 × `401` then `429`; PostgREST anon still
`401`; the private receipt bucket still refuses an unsigned read; and the API
docs are `404` on every path despite `ENABLE_DOCS=true`, because the backend
root is not routed. The single warning is `REDIS_URL`, non-blocking by design —
the limiter runs on the Postgres fallback from `0028`, proven enforcing.

**Why this could not be checked from outside.** Every variable on the Vercel
project is marked *sensitive*, and sensitive variables are write-only:
`vercel env pull` writes the literal `[SENSITIVE]`, `vercel env run` supplies
empty strings, `vercel env ls` shows `Hidden`. A local checker run against
either reports on a configuration that does not exist — it produced three
phantom refusals here. So `main.py` evaluates `production_issues()` on every
boot whatever `APP_ENV` says and logs the verdict; descriptions only, never
values. The answer comes from the one process that holds the real values, which
is also what removed the hazard in the old sequence: nothing had to be flipped
to find out what would happen.

---

## Production state at handoff

| | |
|---|---|
| Schema revision | `0030_tier_share_bounds` — matches repository head |
| PostgREST exposure | **0** tables readable by `anon` or `authenticated` |
| Data integrity | 18/18 invariants hold |
| Stranded workflow records | **0** |
| QA residue | **0** — users 14, reviews 15, products 16, 0 QA markers, 0 orphan rows, 0 rate-limit rows |
| Honesty Fund synthetic rows | 0 (132 exported to `bluntly-rollback/` and removed) |

### Residual risk worth knowing

`supabase_admin`'s default privileges still grant new tables to `anon`, and
`ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin` is refused to the `postgres`
role. So a **future** table created outside our migrations could arrive
anon-readable. Mitigated by two invariants that fail the moment any table
becomes readable by `anon` or `authenticated` — detection, not prevention.
Closing it properly needs Supabase support or a dashboard-level action.

---

## Requirement traceability — original vs. later owner-approved

Where a later owner decision supersedes the signed PRD, the later decision
governs. Recorded here so neither reads as an unmet obligation, and so Figma
frames showing the *original* scope are not mistaken for missing work.

| Original signed requirement | Later owner-approved alignment | Current implementation | Engineering evidence |
|---|---|---|---|
| FR-3: "reviews **publish immediately**" | Publication gate — a review is hidden and auto-queued; a moderator publishes (deviation #30, 2026-07-13) | `create_review` sets `published_at NULL`, `earn_eligible_status pending` | Live: submitted review returned `published_at: null`; published only on moderator action |
| FR-4: seller reviews, seller accounts, seller dashboard | **Descoped** — affiliate-review platform, not a merchant directory (owner, 2026-07-28 / reaffirmed 2026-08-07) | Absent; schema dropped in `0024` | n/a. Figma retains `Seller Review`, `Seller Page`, `Search for Sellers` frames — **obsolete, not a gap** |
| Token economy (balances, transaction history) | **Retired** — superseded by the PHP revenue share (owner, 2026-08-07) | `token_transactions.amount` is a token count, never rendered beside peso figures; `/tokens/balance` retained only as the `wallet_balance` source | Not surfaced in any UI. Old Figma frames showing token balances are obsolete |
| Membership tiers implying purchase | **Not subscriptions** — assigned status levels controlling `revenue_share_bps` and `payout_priority` (ADR-012) | No checkout, no billing; `/membership` reads as a benefits table | e2e asserts the page "explains that tiers are not purchasable" |
| AI critique interface | **Deliberately no UI** for the capstone (owner, 2026-08-07) | Backend endpoints exist and work; frontend surface withheld | No route renders it |
| Payout on request | **Scheduler-driven only** — a sweep over everyone at/above ₱300 with a payout account, in tier order | No "request payout" control anywhere | Absent by design |

**Scope rule applied throughout:** an obsolete Figma frame is not a
requirement. Nothing above will be rebuilt on the strength of a design file
that predates the owner decision retiring it.

---

## Owner-approved changes after the freeze (2026-08-22)

Two product changes the owner authorised after engineering delivery, which
means QA is retesting a build that has moved past `47b5388`.

### A. `/reviews/[id]` desktop redesign

**The defect.** The page carried the Figma frame's orange phone bar at every
width. At 1440px the most important screen in the product had no wordmark, no
search and no navigation — a back-arrow where the site header belongs — and put
a 704px reading column in the middle of the window with grey either side. The
component had two responsive breakpoint usages in 369 lines.

**Now.** The phone bar is phone chrome, hidden from `md` where `SiteHeader`
takes over. At `lg` the page is a reading column beside a 20rem context
sidebar: product card with the Buy action, the FR-2 price panel, the reviewer
and their trust, and related reviews from the same category. The Buy control
appears once, not twice. Mobile is unchanged.

| Width | Header | Reading column | Sidebar |
|---|---|---|---|
| 1440 / 1280 | site | 672px | 320px |
| 1024 | site | 576px | 320px |
| 768 | site | 704px, single column | — |
| 393 | orange phone bar | full width | — |

No horizontal scroll at any width.

### B. `/feed` — new browsing surface

`/` is untouched and does **not** redirect. The landing page argues for the
platform; the feed is for someone who has already decided and wants to see what
people are saying.

**Public on purpose.** Discovery that demands an account is discovery nobody
does, and every review shown is already published. Signing in changes the
ranking, not the access.

**Ranking** reuses the existing `/reviews/feed` endpoint rather than forking a
parallel system. `mode=plain` is identical to what landing, search, category
and profile already depend on. `mode=for-you` adds two transparent steps:

1. reviews in the reader's chosen categories move to the front (stable
   partition, nothing removed),
2. no author and no product may take more than two visible slots.

Both are pure functions with 10 tests, and both are no-ops for a signed-out
reader — the fallback is the same quality-and-recency feed, not an empty one.
`offset` is bounded at 1000: a browsing feed, not an export.

**Moderators** get the ordinary feed. Nothing forces them to `/moderate`.

**Privacy:** both surfaces use the existing `FeedItemOut` serializer, which
carries `has_receipt` as a boolean and no locator, and a `FeedAuthor` that has
never included email or wallet fields.

---

## Owner-approved changes after the freeze (2026-08-26)

A second post-freeze sprint, authorised in the owner's "UI fidelity + anti-AI
design + production quality" and "Request Distribution" briefs. QA is retesting
a build that has moved well past the previous handoff.

**Every number on every new surface is queried.** Where the approved design
shows a figure nothing measures, the surface says so rather than substituting a
plausible one. Those cases are listed under *Documented deviations* below and
are the only places an implementation intentionally differs from its frame.

### C. Request Distribution — new operational analytics

**Where it lives.** `/moderate`, not `/dashboard`. It is moderator-only
operational analytics; `/dashboard` is a contributor's own earnings screen.

**Data source, in the order the brief asked them to be evaluated.**

| Candidate | Verdict |
|---|---|
| Vercel Web Analytics | **Not enabled** for this project — the API returns `Web Analytics not found`. No historical geography exists to backfill. |
| Vercel runtime logs | The connector's token cannot reach this project (403). Not available to the application. |
| Existing backend telemetry | **None existed.** No analytics table; `rate_limit_counters` is a rate limiter, not traffic history. |
| **Vercel edge request headers** | **Chosen.** Present, first-party, free, and privacy-preferable. |

Because nothing historical existed, **collection began the day this shipped**
and the panel says so in its empty state rather than drawing a demonstration
world.

**Geography level.** Country, region and city as the edge resolves them, plus
the edge's own coarse coordinates for the marker. The serving Vercel POP is
kept as a *separate* field and labelled "served via SIN" — it is where the
request was served, not where the reader is. Production data already shows the
distinction: a reader in Parañaque served from `sin1`.

**Count** = total page requests in the window.
**RPS** = `request_count / covered_seconds`, where `covered_seconds` is the span
actually backed by data, never the nominal window. Collection started
recently, so dividing a 30-day window by its full length would report a rate
hundreds of times lower than reality. The denominator is returned to the client
so the UI states what the rate is averaged over.

**What is counted.** Page requests only — not `/api/*`, not prefetches, not RSC
payload fetches, not assets. Excluding `/api` also stops the beacon (itself an
API request) from recursing.

**Retention.** 90 days of hourly buckets, enforced in application code, tied to
the opening of a new bucket. There is no scheduler behind it because production
has no Redis broker, and a retention policy nothing executes is not a policy.
The published privacy policy already discloses "basic device, log, and
analytics information" with general retention; a hard 90-day cap on aggregates
is stricter, so no policy change is implied.

**Privacy.** No IP address is read, sent, stored or logged anywhere in this
path — the edge resolves location before the request reaches the application,
so the address never enters it. The table has no user column, so a row cannot be
joined back to a person. A test asserts no address or identity appears in the
API response.

**API.** `GET /api/v1/admin/analytics/request-distribution?metric=count|rps&range=24h|7d|30d|90d&limit=N`
— moderator only, aggregate geography only. An unknown range is a 422 rather
than a silent fallback: a dashboard that quietly answers a different question
than the one asked is worse than one that refuses.

**UI.** Map plus ranked list, where **the list is the primary reading**. Every
figure appears as text beside its bar; the bar restates the number above it;
each marker carries its own value. No charting or WebGL dependency — the map is
inline SVG whose code is smaller than a library's import would be, and the panel
ships only to `/moderate` (verified absent from `/`, `/feed` and `/search`).
Expand uses a native `<dialog>`, so Escape, focus containment and focus
restoration come from the platform.

**Responsive.** Verified 390 / 768 / 1440: map above list on narrow screens,
side by side on wide, no horizontal overflow at any width.

### D. `/dashboard` — rebuilt to the approved reviewer frame

Was a plain earnings list against Figma frame `5572:7130` (orange hero,
floating action bar, stats card with area chart, medal-ranked review list with
sparklines). Classified `MAJOR_FIDELITY_GAP`; now built to the frame's own
geometry.

Real sources: the headline is net recognised commission (reversals **included**,
so it is the net position); "Earned" is the selected window; "Total Views" comes
from a new per-review view counter; "helped" is `helpful_votes`; per-review
sparklines are that review's daily views.

Wallet, payouts and tier detail keep their place below — the frame is silent
about them, and deleting working payout UI to match a silent frame would be a
regression.

### E. `/moderate` — rebuilt as the approved admin console

The owner's repeated "still not 1:1" was **structural, not cosmetic**. Admin
frame `5017:1738` is a console — a 220px sidebar with four labelled groups and a
user card, beside a working area with four headline counts, a recent-activity
feed and a queue breakdown. `/moderate` was a single scrolling page. No amount
of spacing work would have closed that.

All figures queried. The queue count uses the **same predicate as the queue
list** beneath it. "Approved today" is a Manila calendar day, not UTC — a
moderator approving at 08:00 local is 00:00 UTC, and a UTC day would file a
morning's work under yesterday.

`receipt_view` is deliberately excluded from the activity feed: it is the audit
record of a moderator opening someone's proof of purchase, and putting it in a
dashboard feed would advertise private-evidence access as routine.

### F. Affiliate — canonical import, provider identity, real reversals

Two latent money defects closed. Both were latent only because production holds
zero commissions.

**Cross-file double credit.** The old idempotency key was
`(filename:sha256, line number)`, so the same order arriving in a *different*
export was credited twice. The key is now the provider's own transaction
identity, measured against the owner's real exports rather than assumed:

| Provider | Key | Result |
|---|---|---|
| Shopee | Order + Conversion + Item + Model + Promotion | 108 distinct in 108 rows |
| Lazada | Sub Order ID | 218 distinct in 218 rows |

**Returns could never reverse.** The old parser drops non-payable rows — and a
return *is* a non-payable row, so it vanished and the earlier `completed` row
stood forever. Every row is kept now: 108/108 and 218/218 retained, including
the 11 Lazada returns and 5 Shopee cancellations previously discarded.

A reversal is a **new opposing entry** pointing at the original, never an edit —
editing destroys the record that money was once recognised, which is the audit
trail.

**Post-payout returns follow the owner's decision.** The wallet is debited only
by what is actually in it; the shortfall is recorded as `unrecovered_amount` and
absorbed by the platform. `wallet_balance >= 0` therefore holds **by
construction**, not because the database refuses the write.

**Withdrawability:** only `completed` recognises. Pending never credits.

**Preview** is a separate endpoint that writes nothing, with totals quantized to
the centavo exactly as the ledger will store them — providers report more
precision than money has (Shopee carries five decimal places), and a preview
total that never matches the entries written afterwards is worse than none.

### G. Images — the `/search` LCP

Root cause was **not** loading priority. Supabase Storage answers
`Cache-Control: no-cache` for every public object in this project, so full-size
files came down on every visit. Fixed at the upload site, the stored metadata
backfilled, and images moved to Supabase's render endpoint (the built-in Next
optimizer is unreachable behind this project's service rewrite — `/_next/image`
404s, which broke every image for ~20 minutes until caught and fixed).

| Page | Image bytes before | After |
|---|---|---|
| landing | 118 KB | 33 KB |
| feed | 984 KB | 51 KB |
| search | 312 KB | 5 KB |
| review | 984 KB | 14 KB |

---

## Anti-AI / generic-template visual audit (2026-08-26)

Run against the heuristics the owner supplied. The rule applied to each was the
owner's own: **an element is not removed because it appears on a list** — the
question is whether it is in Figma, whether it is intentional Bluntly identity,
or whether it is generic template residue.

| Heuristic | Found? | In Figma / intentional? | Verdict |
|---|---|---|---|
| Glass / backdrop blur | 1 — `SiteHeader` sticky bar at 85% opacity | Functional sticky chrome, not decoration | **Keep** |
| Gradients | `--brand-gradient` only: welcome, auth shell, dashboard hero, chart fills | Welcome and auth are documented Figma-verbatim; the dashboard hero is its frame's own hero | **Keep** |
| Emoji / sparkle decoration | **0** | — | Clean |
| Over-rounded cards (`rounded-lg/xl/2xl/3xl`) | **0** | Every radius is a `--radius-*` token | Clean |
| Arbitrary pastel/neon hex | 3 — gold/silver/bronze medals | The frame draws medals; metals are literal, not palette drift | **Keep**, documented in place |
| Excessive hover animation | 2 — a 3% image scale on one card | Restrained card affordance on a tokenised duration | **Keep** |
| AI marketing vocabulary ("seamless", "elevate", "supercharge"…) | **0** | — | Clean |
| Excessive em dashes | 51 total: **30** are the site title convention `X — bluntly`; **21** in prose | The 30 are a consistent metadata convention; the 21 are ordinary correct usage at low density across the entire marketing surface | **Keep** |
| Generic three-card sections | 8 `grid-cols-3`, in categories / membership / profile / user | All are content grids (categories, tiers, review lists), none is a "three feature cards" marketing block | **Keep** |
| Unnecessary shadows | 121, of which 118 are `--shadow-card` / `--shadow-hairline-inset` tokens | The remainder are focus rings, which are functional | Clean |
| Repetitive / mixed icon sets | Phosphor in 43 files, **Lucide in 0** | Single consistent library | Clean |

**No removals were required.** Every pattern the heuristics name is either
absent, expressed through a design token, or traceable to an approved frame.

### Loading states

Audited every `loading.tsx`, and the routes that had none.

* The **only** loading state that paints the brand orange is `/dashboard`, and
  that is correct: its hero is orange at every width in its own frame. This is
  the opposite of the `/reviews/[id]` defect the owner reported, where orange
  was phone-only chrome being painted at 1440px.
* Five server-fetching routes rendered **nothing at all** while awaiting the
  backend — `/moderate`, `/profile`, `/u/[id]`, `/questions/[id]`,
  `/contracts`. All now have neutral, layout-faithful skeletons. `/moderate`
  gets the console's own shape, including the real 220px rail, so the working
  area does not start wide and snap narrower when the sidebar arrives.

---

## Documented deviations from approved frames (2026-08-26)

Each is a place the implementation intentionally differs from its Figma frame.

### Avg. Read time — `/dashboard`

| | |
|---|---|
| **Figma** | A third stat reading "4m 3s". |
| **Implementation** | "—", labelled "Not measured yet". |
| **Why required** | Nothing measures read time. Doing so means timing how long a reader stays on a page — reader-behaviour tracking, not the aggregate counting used elsewhere — and needs a privacy ruling that is the owner's, not engineering's. The API returns `null` and names the field in `unavailable[]`. |
| **Evidence** | Brief: "Do not fake analytics"; "Dashboard graphs and analytics must use real data". |
| **To close** | Owner ruling on whether reader-session timing is acceptable, and a privacy-policy line if so. |

### Unbuilt admin destinations — `/moderate`

| | |
|---|---|
| **Figma** | Ten navigation items, rendered identically. |
| **Implementation** | The three with a real destination link; the other seven keep position and label, marked "Soon", not focusable. |
| **Why required** | Products, Sellers, Reviewers, Affiliate Links, Honesty Fund, Activity Log and Settings have no page behind them. Shipping them live would put seven dead controls in an admin tool's primary navigation. |
| **Evidence** | Brief: "Do not implement a dead fullscreen icon… omit it rather than leaving fake controls." |
| **To close** | Build the seven screens, or owner confirmation that they are out of scope for this release. |

---

## Still blocked (2026-08-26)

| Item | Status | What unblocks it |
|---|---|---|
| Authenticated visual verification of `/dashboard` and `/moderate` **in situ** | `BLOCKED AUTH` | A moderator browser session. The Claude-in-Chrome channel is not connected, and engineering will not mint a privileged production token. Both surfaces were verified component-by-component against fixture data at 390/768/1280/1440 with zero console errors, and their APIs verified against production data — but neither has been seen rendered end-to-end behind a real login. |
| `Avg. Read time` | `OWNER DECISION REQUIRED` | See the deviation above. |
| PayPal payouts | `BLOCKED EXTERNAL` | Unchanged — sandbox credentials absent. |
| **CI `Backend (isolated database)` exceeds its 75-minute step timeout** | `BLOCKED EXTERNAL` | A workflow change. The `Backend (isolated database)` step has a 75-minute ceiling and the suite took 67:53 on its last completed run — 831 tests against a database in Singapore from a GitHub runner, ~4.9s each, almost all network latency. It tipped over the ceiling once this sprint. Avoidable round trips were removed (652 in one test alone) to buy headroom back, but the structural fixes — `pytest-xdist`, or a database closer to the runner — both need an edit under `.github/workflows`, which this credential cannot push. **Anyone with the `workflow` scope can fix it in one line** — raise `timeout-minutes` on that step.

**Current state, stated precisely.** Three of the four CI jobs pass on every run: `Frontend`, `Backend (no database)` and `Production guard`. The fourth does not fail on an assertion — it is killed by the step timeout. Its last run that finished reported **831 passed, 9 failed**; all nine were one defect (the importer setting a column the table does not have), which is fixed and covered by two database-free guards, each verified by reintroducing its bug.

Parallelising was considered and rejected rather than attempted: `pytest-xdist` is not installed, and the workflow's own comment records that the session-pooler credential caps at about four concurrent clients, where over-subscribing "produces setup errors late in the run that look like unrelated test failures". Introducing that failure mode into the money path, on a suite that takes 75 minutes per attempt to evaluate, is a worse outcome than a red badge with a known cause. |

---

## Verification evidence (2026-08-26)

Measured against production, in this order. The order is the point: after the
`/_next/image` incident, **a Lighthouse score from a page with missing assets
is not evidence**, so assets are verified to render before any score is quoted.

### 1. Production assets render

`e2e/images.spec.ts`, run against `https://www.bluntly.ph`:
**20/20 passing** across chromium, firefox, webkit, mobile-chrome and
mobile-safari. Each page asserts the request succeeded, `naturalWidth > 0`
(it decoded, not merely responded), the drawn box did not collapse, the
response is cacheable, and there were no console or network errors.

This test found a real WebKit behaviour on its first run and, on inspection,
the fault was the test's own scrolling rather than the product — recorded in
the spec so nobody re-derives it.

### 2. Public performance, after assets were confirmed

| Page | Perf | A11y | Best practices | SEO | LCP | CLS | Console errors |
|---|---|---|---|---|---|---|---|
| landing | 93–95 | 96 | 100 | 100 | 3.0s | 0 | 0 |
| feed | 95 | 95 | 100 | 100 | 3.0s | 0 | 0 |
| search | 93 | 96 | 100 | 100 | 3.2s | 0 | 0 |
| review | 98 | 92 | 100 | 100 | 2.4s | 0 | 0 |

Landing was measured four times because a single run immediately after a deploy
read 81; the repeat runs were 93/95/93/95 with a 31ms TTFB, so that reading was
a cold cache rather than a regression. Single Lighthouse runs are not quoted as
results anywhere in this document.

### 3. Regression suite

Full Playwright suite against production: **60 passed, 6 skipped, 0 failures** —
route guards, redirect safety, responsive layout, accessibility and console
health all intact after the sprint.

### 4. Backend

**712 tests pass locally; 831 in CI** (the difference is the ~120 that need
Postgres and skip on developer machines). Ruff clean, TypeScript clean, ESLint
clean, production build clean.

CI caught one genuine defect this sprint that every local gate missed — the
importer set a column the table does not have — because the importer's tests
all require a database. Two database-free guards were added so that class of
error fails in seconds rather than 68 minutes, and both were verified by
reintroducing the bug.

### 5. Production integrity

`scripts/check_invariants.py` against production: **all 20 invariants hold**,
including `wallet_balance >= 0`, the commission split identity, reversal
opposition, and that no `public` table is readable by `anon` or `authenticated`.

### 6. Authorization

Every endpoint added this sprint denies an anonymous caller:

| Endpoint | Anonymous |
|---|---|
| `GET /admin/analytics/overview` | 401 |
| `GET /admin/analytics/request-distribution` | 401 |
| `GET /admin/analytics/geo-probe` | 401 |
| `GET /users/me/dashboard` | 401 |
| `POST /admin/affiliate/preview` | 401 |
| `POST /admin/affiliate/import` | 401 |
| `GET /internal/traffic` | 405 (write-only) |

`/dashboard`, `/moderate` and `/profile` all 307 to `/login?next=…`.

The one unauthenticated write surface — the traffic beacon — was probed
directly against production: oversized values, over-long country codes,
out-of-range coordinates, wrong types and malformed UUIDs are all 422; unknown
keys (`is_admin`, `role`) are dropped rather than bound; a SQL-shaped string
was stored as a literal with `users` intact afterwards. Markup and control
characters are now rejected so a moderator's chart stays legible.

---

## QA retest pack

Reproducible user workflows, not internal engineering checks. Production base
URL is `https://www.bluntly.ph`.

### 1. Moderation lifecycle (defect #1 — highest value)

- **Precondition:** a moderator account; at least one unpublished review in the queue.
- **Steps:** open the moderation queue → publish a review → confirm it appears publicly → unpublish it → **return to the queue**.
- **Expected:** after unpublishing, the review is *still listed in the queue* and can still be published or rejected. It must not vanish from both the site and the queue.
- **Fix reference:** `b7a506a`; guarded by invariant #18, which must stay at zero.

### 2. Reviewer profile — missing vs. real (defect #3)

- **Precondition:** none; signed out is fine.
- **Steps:** visit `/u/00000000-0000-0000-0000-00000000dead`, then a real reviewer profile linked from any review card.
- **Expected:** the missing one shows "Reviewer not found." and its HTML carries `<meta name="robots" content="noindex">`; the real one renders the profile and carries **no** noindex.
- **Fix reference:** `c9b52ff`.

### 3. Auth rate limiting

- **Precondition:** a source address that has not just been rate-limited; use a nonexistent account such as `qa-probe@example.invalid`.
- **Steps:** attempt login with a wrong password 11 times in under a minute.
- **Expected:** attempts 1–10 return `401`; the 11th returns `429` with `application/problem+json` and a `retry_after_seconds` field.
- **Note:** worth running from a different network than engineering used, since the limit is keyed per address.

### 4. Full review lifecycle with a real proof photo

- **Precondition:** a reviewer account and a genuine product photo.
- **Steps:** submit a review **with** a photo uploaded through the composer → confirm it is queued and unpublished → have a moderator publish it.
- **Expected:** verification status is **verified** (engineering has only verified the *unverified* path — that a review with no owned photo is not verified). A review whose `photo_url` points at an object the author does not own must stay unverified.
- **Why QA:** needs a real upload with real fixtures.

### 5. Publication gate from a reader's view

- **Precondition:** a freshly submitted, unpublished review.
- **Steps:** sign out, try to reach the review by direct URL; check it is absent from feed, search and the product page; confirm the author can still see it.
- **Expected:** `404` for anonymous readers, visible to its author, absent from all public listings.

### 6. `/feed` browsing (new)

- **Precondition:** signed out, then signed in with interests set.
- **Steps:** open `/feed`; switch between "For you" and "Recent"; page through with Older/Newer; open a card into the full review; check `/` still loads as the landing page and does not redirect.
- **Expected:** reviews render signed out; "Recent" is chronological; a card links to `/reviews/[id]`; signed in with interests, those categories appear first; no author or product occupies more than two of the visible rows.
- **Widths:** rails at 1440/1280, left rail only at 1024, neither at 768/393, and no sideways scroll.

### 7. `/reviews/[id]` desktop structure (redesigned)

- **Precondition:** any published review.
- **Steps:** load at 1440, 1280, 1024, 768 and 393.
- **Expected:** site header at 768 and above with **no** orange phone bar; sidebar present at 1024 and above carrying product, price, reviewer and related reviews; orange bar returns at 393; one Buy control per screen; no horizontal scroll at any width.

### 8. Environment guard (engineering-facing, but retestable)

- **Steps:** from the **repository root** — not `backend/` — run any command that invokes `require_non_production`.
- **Expected:** it reports `PRODUCTION` and refuses. Defect #2 was invisible from `backend/` and only appeared from the repo root, so the working directory is the whole point of this test.
- **Fix reference:** `ea21b47`.

**Not for QA:** FR-4 (descoped), FR-8 layer 3 (no provider procured), payout
execution (no sandbox credentials).
