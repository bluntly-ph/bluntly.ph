# Bluntly.ph — Build Milestones & Roadmap

> **Source:** `[DRAFT] bluntly.ph` capstone manuscript (PUP CCIS, June 2026). Sequencing honors the spec's own implementation plan (Development Jun–Sep 2026 → Testing Oct 2026 → Evaluation Nov–Dec 2026 → Documentation Jan 2027) and its stated Seeding→Post-Seeding phasing. Owners: **Dev team** = the four-person capstone team; where AI-assisted development is used, **Opus-class** models suit the algorithmic/ambiguous work and **Sonnet-class** models suit well-specified CRUD/UI implementation.
>
> Legend: 🔒 = blocked on an external dependency · 🟡 = currently manual by design, sequenced for later automation · ❓ = unscoped in the spec, must be specified before build.

---

## M0 — Foundations & Spec Closure (now → early development)

**Scope**
- Resolve blocking ambiguities *before* code depends on them: identity architecture (Supabase Auth vs. FastAPI/Redis sessions), cloud provider selection, `reputation_score` formula, Wilson time-decay/velocity/reciprocity parameters, `verification_tier` and `member_type` semantics, answer-level `earn_eligible` in/out decision. ❓ (all flagged in PRD §8 / Architecture §8)
- Stand up repo, CI, staging→production pipeline with rollback; environments for Supabase (Postgres, RLS, Storage), Redis, Celery.
- Implement the database schema per the Data Dictionary (15 tables) with migrations; decide the update path for denormalized product/seller aggregates.
- Governed **OpenAPI** contract from FastAPI (versioning + error schema) — closes the REST/OpenAPI gap.
- Baseline security hardening: modern password KDF, rate limiting on auth/registration (unspecified in spec — add ❓), TLS everywhere.
- Privacy foundations: privacy notice, consent capture for evaluation participants, session-PII retention jobs (30/90-day rules), DPA/GDPR-equivalent checklist (subject-rights intake path, breach-notification runbook, NPC registration assessment). 
- Accessibility baseline: adopt **WCAG 2.1 AA** as a definition-of-done for all UI work (absent from spec — add ❓).

**Dependencies:** none (this milestone *is* the prerequisite).
**Suggested owner:** Dev team; Opus-class for parameter design/threat-model decisions, Sonnet-class for scaffolding.
**Done when:** All ❓ items above have written decisions; schema migrated to staging; CI deploys green; OpenAPI doc published; UREC ethical-clearance submission prepared (🔒 required before any participant data collection).

## M1 — Core Contribution Loop (maps to Development phase, Jun–Sep 2026)

**Scope**
- **Accounts & profiles (UC-01):** email verification, login, notifications, profile management; roles user/seller/moderator; RBAC + RLS.
- **Product catalog & discovery (UC-02):** search/filters, category browse, product pages; URL-based product submission storing `source_url`; **admin canonical-naming workflow** 🟡 (manual by design; automation is M5).
- **Review submission (UC-03):** full structured format, immediate publication, verified/unverified paths, photo upload to Supabase Storage, optional post-publish receipt, price-paid context, stats screen, rejection/re-evaluation notifications.
- **Seller reviews & seller accounts (UC-04):** four-dimension form, overall rating + recommendation, claimed/unclaimed profiles, seller dashboard, store-name cross-check verification 🟡.
- **Q&A (UC-05):** buyer/seller routing, Best Answer, First Responder badge, searchable archive. ❓ Define "relevant product experience" matching before build.
- **Community voting & ranking:** equal-weight visibility votes; time-decayed Wilson Score ranking; velocity flags queued for admin (using M0 parameters).
- **Price observations:** submission (platform, price, date, variant) and the 3-observation panel rule.
- **Product comparison tool.**

**Dependencies:** M0 schema, auth decision, ranking parameters.
**Suggested owner:** Dev team; Sonnet-class for forms/CRUD/dashboards, Opus-class for the ranking/decay implementation.
**Done when:** End-to-end: a user can register, add a product (admin canonicalizes), publish a verified review, review a seller, ask/answer/award Best Answer, vote, submit price observations, and compare products — verified by unit + integration tests listed in §3.4.

## M2 — Incentive Engine & Moderation (completes Development phase)

**Scope**
- **Trust progression:** six stages, unlock criteria, vote-weight multipliers × trust %, 30-day halving, probation zeroing; badges + `user_badges`.
- **earn_eligible system:** Seeding-Phase queue (all verified submissions); moderator review card aggregating proof photo, receipt, plagiarism result, reverse-image result ❓ (provider must be chosen — M0), account history/activity/journey signals; approval → ≥3★ affiliate-link attach 🟡 (link generated manually in the Shopee Affiliate account) + trust badge, ≤2★ → Honesty Fund pool; specific-reason rejection + re-evaluation.
- **Post-Seeding machinery (built now, dormant):** effective-n Wilson computation from `earn_eligible_votes` snapshots, 0.65 @95% auto-queueing, ≥3 Stage 2+ voter check, phase-transition detection at 50 Stage 2+ reviewers, admin fast-track "Admin-referred" labeling, reciprocity/vote-spike flags on the review card. (Unit tests for phase transition are explicitly required by §3.4.1.)
- **Moderation & reporting (UC-07/08):** report reasons, 3-report / Stage-4+ escalation, investigation workflow, penalties + earning/vote-weight suspension, frivolous-report weighting, decision override, anomaly pattern report, audit log.
- **Earnings & payouts (UC-06/09):** sessions + click tracking, commission CSV import & reconciliation 🟡 (manual import by design), 40/30/30 split records, earnings dashboard, PHP 300 PayPal payouts 🔒 (PayPal account/API onboarding), monthly Honesty Fund Celery job (Honesty Score = trust-weighted helpfulness × price bracket), moderator-only earnings breakdown, IP-detection flags.

**Dependencies:** M1 content loop; M0 parameter decisions; Shopee Affiliate account in good standing 🔒; PayPal integration 🔒.
**Suggested owner:** Dev team; Opus-class for effective-n/Wilson/collusion logic and money-movement paths, Sonnet-class for dashboards.
**Done when:** Full Seeding-Phase earning path works on staging with simulated CSVs and sandbox PayPal; Post-Seeding logic passes unit/integration tests including phase-transition detection; moderation queue round-trips reports to resolution with notifications.

## M3 — Hardening, Testing & Compliance (maps to Testing phase, Oct 2026)

**Scope**
- Execute the spec's test program: unit, integration, system, security (all seven deterrence layers + RBAC + session expiry + RA 10173 checks), usability, compatibility (Chrome/Firefox/Safari/Edge; desktop→mobile), and **simulated load testing**. ❓ Set the quantitative targets the spec omits (p95 latency, error budget, concurrency) so "performance" is falsifiable.
- WCAG 2.1 AA audit and fixes (screen reader, keyboard, contrast, alt text on proof-image flows).
- ISO/IEC 27001-oriented gap pass: risk register, incident-response runbook, backup **restore drill** with defined RTO/RPO, dependency/vulnerability scanning.
- Seed the pilot category (electronics & accessories: power banks, BT earphones, portable fans, USB accessories) per the LKI recommendation.
- Finalize evaluation instruments: pre-use profile questionnaire, 40-item ISO/IEC 25010 post-use instrument (IT-expert content validation 🔒), Google Forms setup, automated metrics collection.

**Dependencies:** M1+M2 feature-complete; UREC clearance 🔒 must be granted before participant recruitment.
**Suggested owner:** Dev team + platform administrator; Sonnet-class for test authoring at scale, Opus-class for security review.
**Done when:** All §3.4 test suites pass; load test meets the M3-defined targets; accessibility audit issues resolved or waived with rationale; instruments validated; UREC clearance in hand.

## M4 — Evaluation Launch & Operations (Nov–Dec 2026)

**Scope**
- Recruit 100+ participants (convenience sampling via social media); onboard with informed consent and the PayPal/PHP-300 disclosure required by §3.9.
- Operate the **Seeding Phase**: single-moderator earn_eligible processing 🟡, manual canonical naming 🟡, manual affiliate link generation 🟡, monthly commission CSV import 🟡, first live Honesty Fund distribution, live PayPal payouts.
- Continuous metrics collection; incident response; moderation SLAs informally tracked to size M5 automation.
- Administer post-use instrument; run the analysis plan (weighted means, SD, Cronbach's α, pre/post source-consultation comparison, thematic coding across the six problem areas).

**Dependencies:** M3 complete; UREC 🔒; Shopee Affiliate + PayPal live 🔒.
**Suggested owner:** Platform administrator (operations), Dev team (on-call), research team (evaluation).
**Done when:** Two-month window completed; ≥100 participants; all instruments collected; at least one full monthly Honesty Fund cycle and payout batch executed cleanly; findings documented (feeds the Jan 2027 manuscript).

## M5 — Scale & Automation (post-evaluation; explicitly future work in the spec)

Everything here is **flagged in the spec as planned-future or currently manual** — sequence it, don't build it now.

| Item | Status & blocker |
|---|---|
| Post-Seeding Phase go-live (organic Wilson-triggered queueing) | Built in M2, dormant; activates automatically at 50 Stage 2+ reviewers in the pilot category — monitor, don't force |
| AI-assisted pre-screening of submissions before human moderation | 🟡→future; spec notes regulatory/technical constraints on AI moderation in a financial-incentive context ❓ (governance requirements unscoped) |
| NLP classifier replacing fuzzy word matching (trained on platform data) | Future; requires accumulated platform data; interim fuzzy matching stays |
| Partial automation of trust-progression updates via behavioral triggers | Future; define triggers ❓ |
| Automated product name standardization (NLP) | 🔒 Blocked on formal Shopee/Lazada API partnership or data-sharing agreement (ToS prohibits scraping) |
| Automated listing/price/commission ingestion | 🔒 Same ToS/API blocker |
| GCash & Maya payouts | 🔒 Blocked on business permit, BIR, and DTI registration under RA 11967 (Internet Transactions Act) |
| Category expansion beyond electronics & accessories | Organic per spec; gate on moderation capacity |
| Multi-moderator support / moderation team tooling | ❓ Unscoped but implied by the single-moderator limitation — needed before any real growth |
| ISO/IEC 27001-aligned ISMS, formal DPO/NPC registration, WCAG 2.2 uplift | Compliance track for public (non-academic) launch |

**Done when:** Each item has its blocker cleared (partnership signed, registrations granted, data volume sufficient) and a written activation plan; none should be built speculatively while blocked.

---

## Cross-cutting external dependencies (watch list)

1. 🔒 **Shopee/Lazada Terms of Service** — prohibits automated extraction; blocks M5 automation; also the reason M1/M2 contain manual workflows. A formal API/data-sharing partnership is the single highest-leverage unlock.
2. 🔒 **PUP UREC ethical clearance** — gates all participant data collection (M3 recruitment prep, M4 launch).
3. 🔒 **Shopee Affiliate Program standing** — the entire revenue model (3–10% commissions) depends on it; account suspension is an existential risk with no fallback in the spec.
4. 🔒 **PayPal** — sole payout rail for the evaluation; onboarding, KYC, and PH disbursement constraints unverified in the spec.
5. 🔒 **BIR/DTI/business-permit registration (RA 11967)** — gates GCash/Maya.
6. 🤝 **Laban Konsyumer Inc.** — advisory partnership (Jorge Bandola); informs category strategy and consumer-protection framing; keep engaged through M4 findings.
7. ❓ **Reverse-image-search / plagiarism providers** — third-party choice pending; triggers a privacy assessment (user photos leaving the platform).
