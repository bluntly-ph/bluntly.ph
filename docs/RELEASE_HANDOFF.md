# Release handoff — engineering → QA

**Prepared 2026-08-21.** Covers the full-stack engagement (frontend + backend
agreements) against the capstone PRD as amended by `docs/DEVIATIONS.md` and the
owner's scope decisions.

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
| Backend — pytest | **582 passed**, 133 skipped |
| Backend — environment guard tests | **27 passed** |
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

| Item | Marker | Exact action required |
|---|---|---|
| **GitHub CI activation** | `GITHUB_CI = BLOCKED_AUTH` | The credential available here lacks GitHub's `workflow` OAuth scope; the push is rejected with `refusing to allow an OAuth App to create or update workflow .github/workflows/ci.yml without workflow scope`. From a credential that has the scope: `mkdir -p .github/workflows && git mv docs/ci/ci.yml .github/workflows/ci.yml && git commit -m "ci: activate release verification" && git push` |
| **`APP_ENV=production`** | `OWNER DECISION REQUIRED` | Not an auth problem: the Vercel connector exposes **no environment-variable capability at all**, so this is a dashboard or CLI action regardless of scope. One refusal stands in the way — see below |
| **Vercel project API** | `VERCEL_PROJECT_API = BLOCKED_AUTH` | The token sees team `bluntlyph` but `404`s on the project. Re-authorise the Vercel connector with project-level access to `bluntly-ph` in team `bluntlyph`. This would unlock deployment and runtime-log inspection; it would **not** unlock env vars |
| **PayPal sandbox** | `PAYPAL_SANDBOX = BLOCKED_EXTERNAL_ZIENT` | Zient to provide sandbox credentials. The acceptance sequence runs automatically once they are in the authorised environment |
| **FR-8 layer 3** | `OWNER DECISION REQUIRED` | Select and procure a reverse-image-search provider. The PRD names none |
| **Isolated test DB secrets** | `OWNER DECISION REQUIRED` | Add `TEST_SUPABASE_SESSION_POOLER`, `TEST_SUPABASE_URL`, `TEST_SUPABASE_SECRET_KEY` to GitHub Actions secrets to switch on `backend-db-tests` and close the 133-skip gap |

### The one thing standing between here and `APP_ENV=production`

Evaluated against the repo's copy of the production values, with `APP_ENV`
forced locally only — **nothing in Vercel was touched**:

```
NOT READY - 1 issue(s).
  - CORS_ORIGINS still points at localhost; a production browser origin
    would be refused.
```

`CORS_ORIGINS` is unset and falls back to a localhost default. Nothing is broken
by that today — the browser never calls the API cross-origin; the Next server
proxies server-side and preflight answers `400` for every origin, which is
exactly why it went unnoticed. The check tests the configured string, so it
would still refuse the boot.

```
CORS_ORIGINS=https://www.bluntly.ph,https://bluntly.ph
```

**Confirm against the real Vercel values before flipping the flag** — the above
is a developer's copy and is not guaranteed to match:

```bash
vercel env pull prod.env --environment=production
cd backend && python -m scripts.check_production_config --env-file ../prod.env --strict
rm ../prod.env
```

It prints descriptions, never values (verified with a marker secret: zero
occurrences), so the output is safe to paste into a ticket. Only set
`APP_ENV=production` once it prints `READY`. **No configuration change should be
used as a discovery mechanism** — a failed boot shows as a 500 from every route.

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

## What engineering is asking QA to retest

Ranked. Items 1–3 are the fixes from this sprint; 4–5 are areas engineering
exercised but cannot sign off on itself.

1. **Moderation lifecycle** — publish, unpublish, reject, and confirm an
   unpublished review is still reachable in the queue and still actionable.
   This is defect #1 and the highest-value retest.
2. **Reviewer profile 404s** — `/u/<nonexistent>` should render the reviewer
   404 and carry `noindex`; a real profile should not.
3. **Environment guard** — confirm automated commands still refuse a production
   target, from more than one working directory. Defect #2 was invisible from
   `backend/` and only appeared from the repo root.
4. **Auth rate limiting** — independent confirmation of the 10/11 threshold,
   ideally from a different source address than engineering used.
5. **Full review lifecycle with a real proof photo** — engineering verified the
   unverified path (no owned photo ⇒ unverified). The *verified* path needs a
   real receipt upload, which is better exercised by QA with real fixtures.

Not for QA: FR-4 (descoped), FR-8 layer 3 (never procured), payout execution
(no sandbox credentials).
