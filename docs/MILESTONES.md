# Bluntly.ph — Delivery Milestones (M1–M3)

> Authoritative build milestones provided by the product owner (2026-07-12).
> These **supersede** the milestone sequencing in `03-bluntly-ph-roadmap.md` where
> they differ. The earlier "M0 Foundations" work (see `superpowers/specs/`) remains
> the technical base these build on. Reconciliation notes are at the bottom.

> **This file tracks the BACKEND track.** The frontend is a separate track with its own
> milestones (FE-M1 core layout & auth, FE-M2 core feature screens, FE-M3 remaining screens &
> full delivery) and its own documentation suite in [`frontend/`](frontend/index.md). The
> frontend consumes this backend through [`FRONTEND_INTEGRATION.md`](FRONTEND_INTEGRATION.md)
> and [`openapi.json`](openapi.json).

## Milestone 1 — Core System Foundation ✅ DONE (2026-07-12)
FastAPI application with **JWT/OAuth2 authentication**, user registration and login,
PostgreSQL database schema (**users, reviews, membership tiers, reputation**),
**review submission and version history** API endpoints, **membership tier
management (Special, Founding, Standard)**, and **basic AI critique integration via
OpenAI or Claude API**.

**As built** (on the M0 foundation): FastAPI-native Argon2id + HS256 JWT auth
(`/auth/register`, `/auth/login`, `/auth/me`; ADR-010/011); `membership_tiers` table
+ `users.membership_tier` (ADR-012); review submission with immediate verified/
unverified status and edit-creates-a-version history (`/reviews`, `/reviews/{id}`,
`/reviews/{id}/versions[/{n}]`); provider-abstracted AI critique defaulting to a
no-key stub (`/ai/critique`, `/reviews/{id}/critique`; ADR-013). Schema grew 15 → 17
tables. Verified end-to-end (register → review → version → critique) with 54 passing
tests. See `superpowers/specs/` and `DEVIATIONS.md` §M1.

## Milestone 2 — Reputation & Trust Systems ✅ DONE (2026-07-14)
**Wilson Score Interval** for seller and product trust ratings, **fake/shill review
detection**, **collusion detection** for coordinated fake-review networks, **trust
threshold configuration** (minimum score for seller/product visibility),
**upvote/downvote** with anti-manipulation measures, **affiliate link generation and
attribution for Shopee/Lazada/Amazon**, **tier-based revenue split calculation**, and
**token economy data models with transaction history**.

> **Slice 1 ✅ DONE (2026-07-13):** the moderator-manual **referral/affiliate link
> flow** (publication gate → manual link attach → click attribution) — spec
> `superpowers/specs/2026-07-13-referral-link-flow-design.md`.
>
> **Slices 2–8 ✅ DONE (2026-07-14, one session per plan
> `superpowers/specs/2026-07-13-m2-remainder-master-plan.md`):** community
> voting + time-decayed Wilson ranking (`review_votes`, `?sort=wilson`, nightly
> re-decay) · trust progression wiring (reputation/stage recompute + stage badges,
> `GET /users/{id}/trust`) · seller reviews + product/seller trust ratings +
> config-driven visibility thresholds (default off) · advisory fraud signals on
> the moderator queue (velocity, collusion, pg_trgm duplicate content — never
> auto-block) · commission CSV reconciliation with the tier-based revenue split
> (30% Honesty Fund fixed; reviewer bps by tier, snapshotted) · token economy
> (append-only `token_transactions` ledger + publish/commission earning hooks) ·
> real Celery bodies for PII retention and Honesty Fund distribution (+ admin
> trigger endpoint). Migrations 0005–0009 applied to **local and Supabase**;
> verified: pytest 89/89 and `api_smoke` 79/79 (incl. concurrency burst, 0 server
> errors) on **both** environments. Acceptance plan: `M2_TEST_PLAN.md`;
> deviations §35–44 in `DEVIATIONS.md`.

## Milestone 3 — Full System Delivery ⚠️ BUILT, NOT DEPLOYED (2026-07-16)
**Request board** with AI validation and **dynamic reward calculation**, **earnings
processing and payment scheduling by membership tier**, **contract duration tracking
and renewal/buyout logic**, **web scraping pipeline for affiliate performance data
(Scrapy + proxy rotation)**, **end-to-end frontend integration**, **load testing**,
and full system **deployed and production-ready**.

> **Slices 9–13 ✅ DONE + slice 14 partially (2026-07-16).** Request board with
> AI validation and dynamic token rewards (escrow → up-vote top-up → fulfilment)
> · monetized-review contracts with renewal/buyout, gating the reviewer's share
> at reconciliation · payouts scheduled by membership-tier priority with a PayPal
> Payouts adapter + an always-available manual rail · **affiliate ingestion of the
> REAL Shopee/Lazada exports** (owner decision: manual CSV only; a brand
> partnership is the intended successor) · frontend readiness (OpenAPI, TS types,
> `FRONTEND_INTEGRATION.md`) · load test meeting every pinned target.
> Migrations 0010–0013 on local **and** Supabase. Verified: pytest 141/141 and
> `supabase_verify` 59/59 on both; load test p95 73 ms / 0.0101% errors / zero
> 5xx at 100 users. Plans: `M3_TEST_PLAN.md`, `LOADTEST_RESULTS.md`,
> `AFFILIATE_REPORT_FORMATS.md`; deviations §46–56.
>
> **🔒 NOT done — M3 is not complete until these land:** the **production deploy**
> (owner supplies host + secrets; `PRODUCTION.md` is the runbook) and live PayPal
> sandbox verification (owner supplies credentials; everything else is verified
> via mocks + manual mode). Two operator prerequisites are also outstanding:
> affiliate links must be generated carrying `suggested_sub_id` or commissions
> cannot be attributed, and the moderator queue is a known slow screen (~9 s on
> Supabase) awaiting an owner conversation. **No frontend pages exist** — that was
> always a separate track.
>
> **Fully planned (2026-07-13, final Fable pass):**
> `superpowers/specs/2026-07-13-m3-master-plan.md` — slices 9–14, one **Opus 4.8**
> session each. Owner decisions recorded: contracts = monetized-review revenue-share
> contracts · payouts = PayPal Payouts API (sandbox first, manual fallback) ·
> frontend = backend readiness + integration guide + TS client · **marketplace
> scraping is ruled out** — slice 12 is a decision gate between first-party report
> automation and manual-CSV-only. 🔒 Blockers to supply when reached: PayPal sandbox
> creds (slice 11), slice-12 path choice, production host + secrets (slice 14).

---

## Reconciliation with the original capstone docs / M0

| Area | Original docs / M0 | New milestones | Resolution |
|---|---|---|---|
| **Auth** | ADR-001: Supabase Auth owns identity (JWT via JWKS); no app password storage (ADR-008) | M1: "FastAPI JWT/OAuth2, user registration and login" | **BLOCKING decision** — see below. If FastAPI-native auth is chosen, ADR-001/008 are superseded by a new ADR. |
| **Membership model** | Roles (user/seller/moderator) + 6 trust stages | Membership tiers **Special / Founding / Standard** | Add a distinct `membership_tier` concept; keep trust stages for reputation. |
| **AI** | Deferred to M5; AI moderation flagged as constrained | M1: AI critique (OpenAI or Claude) | Build a provider-abstracted AI critique service; provider = **pending your choice**. |
| **Affiliate platforms** | Shopee / Lazada only | + **Amazon** (M2) | Add `amazon` to the platform enum in M2. |
| **Earnings** | Wallet + PayPal + Honesty Fund | **Token economy** + tier-based splits + payment scheduling | Token-economy data models (M2), payment scheduling (M3). |
| **Marketplace data** | **No scraping** — ToS-prohibited; manual-first admin workflows (MARKETPLACE_INTEGRATION.md) | M3: **Scrapy + proxy rotation** scraping pipeline | ✅ **RESOLVED (2026-07-15, owner):** scraping is ruled out permanently. Ingestion is **manual CSV** of the owner's own affiliate reports, with a first-party brand partnership as the intended successor. No Scrapy, no proxies, no headless browsers exist in the codebase. See `AFFILIATE_REPORT_FORMATS.md`. |
| **New concepts** | — | Request board, contract duration / renewal / buyout, review version history | Net-new; designed when their milestone is reached. |

### ✅ M3 scraping vs. the anti-scraping mandate — RESOLVED (2026-07-15)

The capstone docs treat automated extraction from Shopee/Lazada as a hard ToS
violation, and the entire manual-first design exists because of it. Milestone 3's
"web scraping pipeline (Scrapy + proxy rotation)" would have reversed that.

**Owner decision: no scraping, ever.** Affiliate performance data is ingested by
uploading the reports the owner is already entitled to download from their own
affiliate dashboards (`POST /api/v1/admin/commissions/import`), and a proper
partnership with the marketplaces is the intended long-term replacement. The
milestone text above is left as originally written for the record; this is the
resolution that governs.

Slice 12 implemented that decision against the owner's REAL exports — which
turned out to need real code, not none: see `docs/AFFILIATE_REPORT_FORMATS.md`
and `DEVIATIONS.md` §52–54.
