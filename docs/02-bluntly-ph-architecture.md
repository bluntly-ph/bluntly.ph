# Bluntly.ph — Technical Architecture Document

> **Source:** `[DRAFT] bluntly.ph` capstone manuscript (PUP CCIS, June 2026) — Technical Background (§1.2), Design Specifications (§3.2), Development Tools (§3.3.2), and Test Methodology (§3.4). Items not specified in the source are flagged **[OPEN]**.

---

## 1. System Overview

Bluntly.ph is a cloud-hosted, service-separated web application:

```
                      ┌─────────────┐
   Users ──HTTPS──▶   │ Cloud Load  │──▶ CDN (static assets, edge nodes for PH latency)
 (browser, any device)│  Balancer   │
                      └──────┬──────┘
                             │
                   ┌─────────▼──────────┐        ┌──────────────────────────┐
                   │  Next.js frontend  │──REST──▶│   FastAPI backend (API)  │
                   │  (SSR/SSG, Tailwind│  HTTPS  │  auth, reviews, Q&A,     │
                   │  Zustand/Context,  │         │  trust progression,      │
                   │  TanStack Query)   │         │  affiliate link mgmt,    │
                   └────────────────────┘         │  RBAC at API layer       │
                                                  └───┬──────────────┬───────┘
                                                      │              │
                                       SQLAlchemy ORM │              │ Redis (broker,
                                                      ▼              ▼  sessions, cache)
                                        ┌──────────────────┐   ┌───────────────┐
                                        │ PostgreSQL via   │   │ Celery workers│
                                        │ Supabase (RLS,   │   │ Honesty Fund  │
                                        │ auth, realtime,  │   │ distribution, │
                                        │ media storage,   │   │ commission    │
                                        │ daily backups +  │   │ reconciliation│
                                        │ PITR)            │   └───────────────┘
                                        └──────────────────┘
   External (manual/out-of-band): Shopee Affiliate dashboard (link generation,
   commission CSV export), Lazada commission CSV export, PayPal payout API.
```

All inter-service communication is RESTful over HTTPS with SSL/TLS; verification media replicate across availability zones.

## 2. Components & Responsibilities

| Component | Responsibilities (per spec) |
|---|---|
| **Next.js frontend** | Component-based UI, server-side rendering / static generation, optimized routing; responsive design via TailwindCSS; state via Zustand/Context API; data fetching, loading/error states, and cache invalidation via TanStack Query. |
| **FastAPI backend** | All server-side logic: authentication, review processing, Q&A routing, trust progression, affiliate link management; RBAC enforcement; exposes REST endpoints. |
| **PostgreSQL (Supabase-managed)** | All structured data: users, reviews, seller reviews, Q&A, trust records, price observations, sessions, commissions, moderation logs, earn_eligible votes. Supabase provides hosting, authentication, real-time subscriptions, row-level security, media storage (proof photos, receipts), automated daily backups with point-in-time recovery. |
| **SQLAlchemy** | ORM layer for models, queries, relationships. |
| **Redis** | Session management, caching, Celery message broker. |
| **Celery workers** | Background jobs: Honesty Fund distribution computations, commission reconciliation. |
| **CDN + load balancer** | Static asset delivery from geographically distributed edge nodes; traffic distribution for high availability. |
| **Moderator dashboard (within app)** | earn_eligible queue with review cards (proof photo, receipt, plagiarism result, reverse-image result, account history, activity log, user journey, voter composition, reciprocity/velocity flags), moderation queue, user/trust management, CSV import, earnings breakdown, payout processing, Honesty Fund distribution, analytics, audit log. |
| **Dev toolchain** | VS Code, Git/GitHub, Postman (API testing), Figma (UI/UX prototypes), Affinity (vector assets). Staging→production deployment with rollback procedures. |

### Note on Supabase Auth vs. Redis sessions
The spec assigns authentication to **both** Supabase ("providing … authentication") and to a "secure session-based system backed by Redis" managed by FastAPI. These are two different auth architectures (Supabase JWT vs. server-side sessions). **[OPEN]** — the team must pick one source of truth for identity/session state; running both invites RLS/RBAC mismatches.

## 3. Data Flow (key paths)

1. **Review submission → earning:** User submits structured review + product photo → published immediately (verified) → optional post-publish receipt → earn_eligible queue entry (Seeding: all verified submissions; Post-Seeding: trust-weighted Wilson LB ≥ 0.65 @95% with ≥3 Stage 2+ voters, or admin fast-track) → moderator reviews signal bundle → on approval: ≥3★ ⇒ affiliate link generated (manually, via Shopee Affiliate account) + trust badge; ≤2★ ⇒ Honesty Fund pool.
2. **Vote → rank/gate:** Votes recorded in `earn_eligible_votes` with snapshots (trust stage, trust score, account age, probation, computed `vote_weight`). Community visibility uses equal-weight votes through the time-decayed Wilson Score with velocity flags held for admin review; the gate uses *effective n* (trust-weighted) separately.
3. **Affiliate attribution:** Review affiliate link click → `sessions` row (entry review, product, destination URL, click timestamp, conversion status; UA/IP retained under the PII schedule) → monthly Shopee/Lazada commission CSVs imported by the moderator → reconciled into `commissions` (40/30/30 split fields, CSV source/row reference) → reviewer `wallet_balance` updated.
4. **Payout:** Wallet ≥ PHP 300 → payout request → moderator confirms disbursement via PayPal → `paid_at`, `payout_reference` recorded.
5. **Honesty Fund cycle (monthly, Celery):** Pool = Σ cycle commissions × 30% → eligible ≤2★ earn_eligible reviews scored (trust-weighted helpfulness × price bracket multiplier) → proportional distribution → `honesty_fund_distributions` rows + wallet credit.
6. **Moderation:** Report (reason + optional evidence) → `moderation_logs` → threshold escalation (3 independent reports, or 1 from Stage 4+) → moderator decision → removal/penalty/earning-pause or restore/frivolous-weight-reduction → reporters notified; anomaly patterns escalate to the dev team.

## 4. Data Model (15 tables, from the Data Dictionary)

`users`, `badges`, `user_badges`, `products`, `product_platforms`, `price_history`, `reviews`, `questions`, `answers`, `seller_reviews`, `sessions`, `commissions`, `honesty_fund_distributions`, `moderation_logs`, `earn_eligible_votes`.

Highlights and observations:
- UUID primary keys plus separate human-readable identifier strings (`user_id`, `review_id`, …); FKs with explicit CASCADE / SET NULL behavior; generated column for `trust_level_name`.
- Denormalized aggregates on `products` (rating, counts, aggregated pros/cons JSONB, per-dimension seller aggregates) — requires consistent update paths (triggers or service logic; **[OPEN]** which).
- Vote snapshotting in `earn_eligible_votes` makes gate decisions auditable and immune to retroactive trust changes — a strong design.
- PII lifecycle encoded in `sessions`: user agent purged at 90 days; IP hashed at 30 days, deleted at 90.
- Schema/narrative mismatches to resolve: `reviews.verification_tier` (tier_0 default — tiers undefined); `users.member_type` (undefined); `users.share_percentage` stored as per-user TEXT `'40/30/30'` (a global constant stored redundantly as text — drift risk); `answers.earn_eligible` (answer-level earning undescribed); `commissions.review_id` as a cross-entity TEXT reference to review **or** answer (no FK integrity).

## 5. Tech Stack & Justification (as given in the spec)

| Layer | Choice | Spec's justification |
|---|---|---|
| Frontend | Next.js + TailwindCSS | SSR/SSG and optimized routing; consistent responsive design |
| State/data | Zustand / Context API; TanStack Query | Lightweight state; async calls, loading states, cache invalidation |
| Backend | FastAPI (Python) | High-performance framework for all backend logic |
| ORM | SQLAlchemy | Models, queries, relationships |
| Database | PostgreSQL via Supabase | Managed hosting, auth, realtime, RLS, media storage, backups/PITR |
| Cache/queue | Redis + Celery | Sessions, caching, brokering; background distribution & reconciliation jobs |
| Hosting | "AWS, GCP, or Azure" + LB + CDN | Managed infrastructure, availability, PH-wide latency |

**[OPEN]** Cloud provider is not selected. Note Supabase already hosts on its own cloud; the split of responsibilities between Supabase and the chosen provider (who runs FastAPI/Redis/Celery?) is not specified.

## 6. APIs & Integrations

- **Internal API:** REST over HTTPS, RBAC-protected. FastAPI auto-produces an **OpenAPI 3.x** document — adopt it as the governed contract (versioning, error schema per RFC 9457, auth schemes documented). The spec references "API specification" as a design-phase artifact but does not include it. **[OPEN]**
- **Shopee Affiliate Program:** *Manual* — links generated by the administrator in the registered affiliate account after earn_eligible approval; commission data via *manual CSV export/import*. No API integration (ToS constraint).
- **Lazada:** commission CSV import path exists; the affiliate-account relationship is ambiguous (links are described as generated via the Shopee account only). **[OPEN]**
- **PayPal payout API:** managed by the dev team for disbursements; the moderator confirms payouts. Sandbox-vs-live setup, webhook handling, and failure/retry semantics are unspecified. **[OPEN]**
- **Reverse image search & plagiarism check:** functionally required, provider/implementation unnamed. **[OPEN]**
- **Supabase Storage:** proof photographs and receipts with access-control policies.

## 7. Scalability & Security Considerations

### Scalability
- Stateless API behind a load balancer; Redis cache; CDN; Celery for async heavy work — a reasonable horizontal-scaling baseline.
- The dominant bottleneck is **not technical but operational**: a single human moderator gates every earning decision, canonicalizes every product name, generates every affiliate link, and imports every CSV. The spec itself states this "is not a scalable long-term solution." Scale planning is therefore primarily about moderation throughput (see Roadmap M3/M4).
- Wilson Score and time-decay computations run per content item; velocity detection and reciprocity mapping grow with vote volume — the spec doesn't state whether these are computed online, on schedule (Celery), or on read. **[OPEN]**

### Security (mapped to international standards)
| Control in spec | Standard alignment |
|---|---|
| SSL/TLS everywhere; HTTPS-only APIs | Baseline transport security (ISO/IEC 27002 8.24; OWASP ASVS V9) |
| RBAC at API layer + Supabase RLS | Access control (ISO/IEC 27001 Annex A 5.15/8.3); dual enforcement is good defense-in-depth **if** kept consistent (see §2 auth note) |
| Redis-backed sessions, expiration tested | Session management (OWASP ASVS V3) |
| Password hashing (`password_hash`) | Algorithm/parameters unspecified **[OPEN]** — specify a modern KDF |
| PII retention schedule (sessions) | Storage limitation — GDPR-equivalent principle under RA 10173 |
| Audit log of moderation/admin actions | Logging & accountability (ISO/IEC 27002 8.15) |
| Staging→production with rollback; security patching | Change management (ISO/IEC 27002 8.32) |
| **Gap:** no ISMS, risk register, incident-response plan, vulnerability-management cadence, or third-party (Supabase/PayPal) risk assessment | **ISO/IEC 27001 not addressed** — recommend an Annex A gap analysis before public launch |
| **Gap:** no WCAG requirements | **WCAG 2.1/2.2 AA not addressed** (usability ≠ accessibility) |
| **Gap:** DPA operationalization (subject rights, breach notification, DPO, NPC registration, cross-border transfers) | RA 10173 named, GDPR-equivalent duties not yet designed in |

### Fraud/abuse architecture
Seven-layer deterrence (photo proof, fuzzy matching, reverse image + metadata, IP detection, time-decayed Wilson + velocity, community reporting with thresholds, trust-weighted effective n) plus reciprocity-based collusion detection — all advisory to a human moderator, never auto-blocking. This is coherent for the Seeding Phase; its integrity depends on parameters the spec leaves undefined (thresholds, windows, decay).

## 8. Open Questions & Risks

| # | Question / Risk | Impact |
|---|---|---|
| Q1 | Supabase Auth vs. FastAPI+Redis sessions — which owns identity? | Auth architecture; RLS correctness |
| Q2 | Cloud provider and Supabase/provider responsibility split | Cost, deployment, data residency (cross-border PII transfer under RA 10173) |
| Q3 | Wilson/decay/velocity/reciprocity parameters and compute placement | Core ranking & fraud logic unimplementable as written |
| Q4 | `reputation_score` (trust %) formula | Gate vote weights depend on it |
| Q5 | Reverse-image-search and plagiarism providers (build vs. buy) | Cost, latency, sending user photos to third parties = privacy assessment needed |
| Q6 | Lazada affiliate relationship & cross-platform attribution | Revenue model completeness |
| Q7 | PayPal failure modes, disputes (`is_disputed`), refund/clawback handling when marketplace orders are returned | Wallet integrity; the spec has an `order_status` field but no reversal workflow |
| Q8 | Concurrency of aggregates (product ratings, wallet balances) under simultaneous votes/commissions | Data consistency; needs transactions/locking strategy |
| Q9 | Single-moderator availability = single point of failure for all earnings and moderation | Operational continuity |
| Q10 | IP-based detection vs. mobile CGNAT (many PH users share carrier IPs) | False-positive risk in layer 4 |
| Q11 | No API rate limiting / bot protection mentioned | Registration flooding is only mitigated post-hoc by trust weighting |
| Q12 | Taglish/Filipino support scope (content-only vs. UI i18n) | Localization architecture |
