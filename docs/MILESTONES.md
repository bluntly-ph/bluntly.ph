# Bluntly.ph — Delivery Milestones (M1–M3)

> Authoritative build milestones provided by the product owner (2026-07-12).
> These **supersede** the milestone sequencing in `03-bluntly-ph-roadmap.md` where
> they differ. The earlier "M0 Foundations" work (see `superpowers/specs/`) remains
> the technical base these build on. Reconciliation notes are at the bottom.

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

## Milestone 2 — Reputation & Trust Systems
**Wilson Score Interval** for seller and product trust ratings, **fake/shill review
detection**, **collusion detection** for coordinated fake-review networks, **trust
threshold configuration** (minimum score for seller/product visibility),
**upvote/downvote** with anti-manipulation measures, **affiliate link generation and
attribution for Shopee/Lazada/Amazon**, **tier-based revenue split calculation**, and
**token economy data models with transaction history**.

> **Slice 1 ✅ DONE (2026-07-13):** the moderator-manual **referral/affiliate link
> flow** (publication gate → manual link attach → click attribution) — spec
> `superpowers/specs/2026-07-13-referral-link-flow-design.md`, built and verified
> on local + Supabase.
>
> **Slices 2–8 fully planned (2026-07-13, final Fable pass):**
> `superpowers/specs/2026-07-13-m2-remainder-master-plan.md` pins every remaining
> M2 item to implementation depth — voting+Wilson (2), trust wiring (3),
> seller/product trust + thresholds (4), fraud signals (5), CSV + tiered split (6),
> token economy (7), Celery job bodies (8) — one **Opus 4.8** session per slice, in
> order. **No further planning sessions are needed for M2.**

## Milestone 3 — Full System Delivery
**Request board** with AI validation and **dynamic reward calculation**, **earnings
processing and payment scheduling by membership tier**, **contract duration tracking
and renewal/buyout logic**, **web scraping pipeline for affiliate performance data
(Scrapy + proxy rotation)**, **end-to-end frontend integration**, **load testing**,
and full system **deployed and production-ready**.

---

## Reconciliation with the original capstone docs / M0

| Area | Original docs / M0 | New milestones | Resolution |
|---|---|---|---|
| **Auth** | ADR-001: Supabase Auth owns identity (JWT via JWKS); no app password storage (ADR-008) | M1: "FastAPI JWT/OAuth2, user registration and login" | **BLOCKING decision** — see below. If FastAPI-native auth is chosen, ADR-001/008 are superseded by a new ADR. |
| **Membership model** | Roles (user/seller/moderator) + 6 trust stages | Membership tiers **Special / Founding / Standard** | Add a distinct `membership_tier` concept; keep trust stages for reputation. |
| **AI** | Deferred to M5; AI moderation flagged as constrained | M1: AI critique (OpenAI or Claude) | Build a provider-abstracted AI critique service; provider = **pending your choice**. |
| **Affiliate platforms** | Shopee / Lazada only | + **Amazon** (M2) | Add `amazon` to the platform enum in M2. |
| **Earnings** | Wallet + PayPal + Honesty Fund | **Token economy** + tier-based splits + payment scheduling | Token-economy data models (M2), payment scheduling (M3). |
| **Marketplace data** | **No scraping** — ToS-prohibited; manual-first admin workflows (MARKETPLACE_INTEGRATION.md) | M3: **Scrapy + proxy rotation** scraping pipeline | ⚠️ **DIRECT CONTRADICTION.** The original mandate forbids scraping (Shopee/Lazada ToS). This must be explicitly resolved before M3 — see warning. |
| **New concepts** | — | Request board, contract duration / renewal / buyout, review version history | Net-new; designed when their milestone is reached. |

### ⚠️ M3 scraping vs. the anti-scraping mandate
The capstone docs treat automated extraction from Shopee/Lazada as a hard ToS
violation and the entire manual-first design exists because of it. Milestone 3's
"web scraping pipeline (Scrapy + proxy rotation) for affiliate performance data"
reverses that stance. Before M3 is built this needs an explicit decision:
scrape only *first-party affiliate-dashboard/report* data you are authorized to
access, keep the manual CSV path, or accept the ToS risk. **Not built now; flagged.**
