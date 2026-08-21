# Release handoff — engineering → QA

**Prepared 2026-08-21, revised the same day after GitHub and Vercel were
re-authorised.** Covers the full-stack engagement (frontend + backend
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
| Backend — pytest | **583 passed**, 133 skipped |
| Backend — environment guard tests | **27 passed** |
| **GitHub Actions CI** | **active and green** — guard, backend, frontend all pass on every push |
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

### The 133 skipped backend tests

Every `requires_db` test skips on the development machine, because Docker/WSL
cannot start a local Postgres and the suite is deliberately pinned away from
Supabase — that project **is** production. This is a real coverage gap and it
has bitten once: a `NameError` in `create_review` reached production because
every review-creation test skips itself. Ruff is the compensating control, and
CI's `backend-db-tests` job runs the full suite against the isolated test
project when its secrets are present.

---

## Blocked — needs someone other than engineering

Four items on this list were resolved on 2026-08-21 once GitHub and Vercel were
re-authorised. What follows is only what genuinely remains.

| Item | Marker | Exact action required |
|---|---|---|
| **Isolated test DB — 2 secrets** | `OWNER ACTION — dashboard` | The last engineering-owned item. See below |
| **Isolated test DB — 2 secrets** | `OWNER ACTION — dashboard` | Neither value is retrievable through any API — a DB password can only be *reset*, never read. Supabase → `bluntly-ph-test` → *Settings → Database → Reset database password* (session pooler URI) and *Settings → API* (service_role key), then `gh secret set TEST_SUPABASE_SESSION_POOLER` and `gh secret set TEST_SUPABASE_SECRET_KEY` — both read from the prompt, so neither is ever typed into chat. `TEST_SUPABASE_URL` is already set. This is the only thing standing between the suite and 0 skips |
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
| `TEST_SUPABASE_URL` missing | **Set** — it is a public project URL, not a secret |

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

### 6. Environment guard (engineering-facing, but retestable)

- **Steps:** from the **repository root** — not `backend/` — run any command that invokes `require_non_production`.
- **Expected:** it reports `PRODUCTION` and refuses. Defect #2 was invisible from `backend/` and only appeared from the repo root, so the working directory is the whole point of this test.
- **Fix reference:** `ea21b47`.

**Not for QA:** FR-4 (descoped), FR-8 layer 3 (no provider procured), payout
execution (no sandbox credentials).
