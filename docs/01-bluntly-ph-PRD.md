# Bluntly.ph — Product Requirements Document (PRD)

> **Source:** `[DRAFT] bluntly.ph` capstone manuscript (PUP CCIS, June 2026). This PRD is derived strictly from that document. Items the spec leaves ambiguous or unaddressed are explicitly flagged as **[GAP]** or **[AMBIGUOUS]** rather than assumed.

---

## 1. Overview / Purpose

Bluntly.ph is a web-based **verified product and seller review platform** for Filipino online shoppers. It addresses documented failures of the embedded review systems on dominant Philippine e-commerce platforms (Shopee ~51%, Lazada ~24% of traffic): no proof of purchase required, no review completeness standard, no structured seller evaluation, suppression of negative feedback, and incentive structures that reward volume over substance.

The platform's core thesis is **structural incentive alignment**: authentic contributions are made more *visible* (time-decayed Wilson Score ranking with velocity detection), more *rewarded* (a 40/30/30 affiliate commission split plus an Honesty Fund that pays honest negative reviews), and more *trusted* (proof-of-purchase verification, a seven-layer fraud deterrence framework, and human moderation) than inauthentic ones — within a single Philippines-specific environment supporting Filipino, English, and Taglish content.

The project is a capstone deliverable with a two-month evaluation period (Nov–Dec 2026, 100+ participants), developed in consultation with Laban Konsyumer Inc. (LKI).

## 2. Goals & Success Metrics

### Goals (from the spec's objectives)
1. Implement proof-of-purchase verification (product photograph required at submission; optional post-publish receipt for earn_eligible evaluation).
2. Enforce a structured review format (discussion, verdict with target/anti-target audience, 1–5 star rating, pros/cons, title, photo).
3. Provide a dedicated four-dimension seller review feature (product-to-advertisement accuracy, order completeness, customer service responsiveness, packaging quality) plus overall rating and recommendation indicator.
4. Deliver a hybrid incentive model: 40/30/30 revenue split (platform / reviewer / Honesty Fund), six-stage gamified trust progression, and a two-phase moderation-gated earn_eligible system routing approved reviews to affiliate earnings (≥3 stars) or the Honesty Fund (≤2 stars).
5. Provide a community Q&A system with buyer-or-seller routing and Best Answer awards.
6. Consolidate pre-purchase research into one platform (verified product reviews, seller reviews, community price observations, product comparison tool, Q&A).

### Success metrics (as defined in the spec)
- **Software quality:** Evaluation against **all eight ISO/IEC 25010:2011 characteristics** via a 40-item, five-point Likert instrument (5 items per characteristic); "Meets standard" interpretation requires weighted mean ≥ 3.50; Cronbach's alpha ≥ 0.70 per sub-scale for instrument reliability.
- **Research consolidation impact:** Paired pre-use vs. post-use comparison of the number of external platforms participants consult per purchase decision (baseline context: Filipinos perform 6–7 searches before purchase).
- **Behavioral metrics:** Review submissions, proof-of-purchase upload rates, seller review completions, Q&A participation, vote activity, affiliate link clicks, session duration, trust progression changes — collected automatically over the two-month evaluation.
- **[GAP]** No quantitative business/product KPIs are defined (e.g., target verified-review counts, retention, affiliate conversion, revenue). The only numeric operational threshold is the Seeding→Post-Seeding transition at **50 Stage 2+ verified reviewers in the pilot category**.

### Standards note — ISO/IEC 25010
The spec explicitly commits to the **2011 edition** of ISO/IEC 25010. A newer edition (ISO/IEC 25010:2023, which restructures the model and adds a *Safety* characteristic) exists and is not addressed. If international alignment matters beyond the academic evaluation, either justify the 2011 model or migrate the instrument. **[GAP — standards currency]**

## 3. User Personas / Roles

The spec defines four roles (Table 3) rather than marketing personas:

| Role | Description & responsibilities |
|---|---|
| **Online Shopper / Reviewer** | Filipino online shopper aged 18+ (students, working professionals, older adults) actively using Shopee/Lazada. Registers, searches/reads reviews, submits verified or unverified reviews, participates in Q&A, submits price observations, votes, reports content, earns via affiliate links and Honesty Fund, requests PayPal payouts at ≥ PHP 300. |
| **Seller** | Merchant on a Philippine e-commerce platform (Shopee, Lazada, and others). Registers/claims a seller profile, responds to seller-directed Q&A, monitors reviews and the seller dashboard, complies with anti-manipulation policies. |
| **Platform Administrator (Moderator)** | Operates the earn_eligible queue (proof photo, optional receipt, plagiarism check, reverse image search, account history, activity logs, user journey, voter composition), activates earn_eligible and routes by star rating, generates affiliate links, handles reports and velocity flags, manages trust levels, imports commission CSVs, processes payouts, runs monthly Honesty Fund distributions, reviews audit logs. |
| **Developer / Technical Team** | Maintains infrastructure and deployments, third-party integrations (cloud storage, Shopee affiliate dashboard, PayPal payout API), incident response, security and RA 10173 compliance, coordinates with the administrator and LKI. |

**[GAP]** No demographic/behavioral personas (shopper motivations, seller acquisition profile) are developed beyond survey aggregates; that exercise is outside the source document's scope.

## 4. Functional Requirements

Derived from the Problem–Requirements Matrix (R1–R6), the Requirements–Features Matrix (Table 6), use case reports UC-01–UC-09, and the policies/procedures section.

### FR-1 Account & Profile Management (UC-01)
- Email registration with verification email; login; profile management; notifications. Duplicate-email, invalid-credential, and incomplete-field handling as specified.
- Roles: user, seller, moderator; role-based access control (RBAC) enforced at the API level.
- Language preference: `en`, `fil`, `tl-x-taglish`.

### FR-2 Product Discovery & Consolidation (UC-02; R6)
- Keyword search with filters/sorting; category browsing; product pages with verified reviews and trust badges; browsing does not require an account.
- **Price panel** from community-submitted purchase price observations — displayed only when **≥ 3 independent observations** exist; partial-data empty states specified.
- **Product comparison tool**: side-by-side comparison using verified review scores, seller ratings, and community price data.
- Product ingestion: reviewer pastes a Shopee/Lazada URL (stored as `source_url` reference) or proceeds without one; **the administrator manually sets the canonical product name** (Brand, Line/Series, Key Spec/Variant, Descriptor) to consolidate duplicate listings. *Automated NLP name standardization is explicitly out of scope pending a Shopee/Lazada API partnership (their ToS prohibit scraping).*

### FR-3 Review Submission (UC-03; R1, R2)
- Structured format (all required): free-form discussion; verdict (**yes absolutely / it depends / hard pass**) with explanation, target-audience and anti-target-audience fields; star rating 1–5; pros/cons (suggested or custom, max 10 each); review title; product photograph.
- Reviews **publish immediately**; photograph at submission ⇒ *verified* status; no photo ⇒ *unverified*, no earning eligibility.
- Optional **post-publish receipt/order screenshot** upload as supporting evidence for earn_eligible evaluation.
- Optional price-paid field as purchase context; post-submission stats screen (reviews posted, people helped).
- Rejection notifications include the specific reason; reviewer may resubmit documentation and request re-evaluation.

### FR-4 Seller Reviews & Seller Accounts (UC-04; R3)
- Verified buyers evaluate sellers on four dimensions: **accuracy** (binary: accurate / not the same), **order completeness** (binary: exact order / missing item), **customer service responsiveness** (1–5), **packaging quality** (1–5), plus **overall rating (1–5)** and **would-recommend** indicator. Linked to verified transactions; displayed separately from product reviews.
- Sellers register and **claim unclaimed profiles**; manage business info; view dimension aggregates, rating trends, review volume, and Q&A activity on a seller dashboard; respond publicly to seller-directed Q&A. Claim conflicts route to the administrator; policy-violating seller responses are flagged to moderation.
- Seller verification is limited to **cross-checking store names on submitted proof of purchase against publicly visible marketplace listings** (stated limitation).

### FR-5 Community Q&A (UC-05; R5)
- Buyers direct questions to **other buyers or to the seller**; the system routes and notifies accordingly.
- **Best Answer** award (one per question) updates responder trust score; **First Responder badge** auto-awarded for the first answer within 24 hours.
- Answers ranked by the time-decayed Wilson Score; buyers may return post-purchase to confirm/correct advice, building a searchable archive.
- **[AMBIGUOUS]** "Routes to registered users with relevant product experience" — the matching logic (who counts as relevant, how notified) is not specified.

### FR-6 Incentives, earn_eligible & Payouts (UC-06; R4)
- **Revenue split:** every affiliate commission splits 40% platform operations / 30% reviewer / 30% Honesty Fund. Commission rates 3–10% by category per the Shopee Affiliate Program. The split is **confidential**: reviewer dashboards show earned amounts only; the platform-wide breakdown is moderator-only.
- **earn_eligible gate (two phases):**
  - *Seeding Phase* (until ≥ 50 Stage 2+ verified reviewers in the pilot category): direct moderator review of all qualifying submissions; no Wilson threshold.
  - *Post-Seeding Phase*: auto-queue when trust-weighted Wilson Score lower bound ≥ **0.65 at 95% confidence** (computed on *effective n*) **and** ≥ 3 distinct Stage 2+ voters. The moderator retains final approval in both phases. A moderator **fast-track referral** queues any review as "Admin-referred."
- **Routing:** approved ≥ 3-star reviews get a generated affiliate link + verified trust badge; approved ≤ 2-star reviews go to the **Honesty Fund**, weighted by **Honesty Score = trust-weighted helpfulness votes × price bracket multiplier** (1.0× below PHP 500; 1.5× PHP 500–1,499; 2.0× PHP 1,500+).
- **Honesty Fund:** monthly pool = 30% of all cycle commissions; individual payout = (review's Honesty Score ÷ total eligible Honesty Scores) × pool.
- **Payouts:** PayPal only; minimum wallet threshold **PHP 300** (≈43% of the NCR daily minimum wage, Wage Order NCR-26). GCash/Maya are future work pending business permit, BIR, and DTI registration under RA 11967.
- Earnings Dashboard: totals, per-review affiliate earnings, Honesty Fund history, trust level/badges, gate status per review, link click/conversion performance, payout requests.

### FR-7 Trust Progression (R4)
Six stages with escalating privileges and earn_eligible vote weights (multiplied by trust score percentage from Stage 2 up):

| Stage | Name | Unlock criteria | earn_eligible vote weight |
|---|---|---|---|
| 0 | Newcomer | Registration | 0 (no gate voting; no incentives; 30-day maturation) |
| 1 | Contributor | First review | 0.25 |
| 2 | Verified Buyer | First verified review | 1.0 × trust % (affiliate earning unlocks) |
| 3 | Established Reviewer | ≥5 verified reviews, ≥70% helpfulness | 1.5 × trust % (higher search visibility) |
| 4 | Trusted Reviewer | ≥15 verified reviews, 0 strikes, ≥3 Best Answers, ≥80% helpfulness | 2.0 × trust % (gold badge, priority Q&A, higher Honesty Fund share, relaxed proof, instant report escalation) |
| 5 | Community Expert | ≥50 verified reviews, ≥90% helpfulness, ≥6 months active | 3.0 × trust % (specialty badges, governance voice, beta access, highest earning multiplier) |

- Accounts < 30 days old: vote weight halved. Probation: earn_eligible vote weight = 0. Community *visibility* votes are equal-weight for all stages and independent of gate voting.
- **[AMBIGUOUS]** The "trust score percentage" (`reputation_score`, 0–100) has no defined computation formula. Stage 4's "relaxed proof requirements" and Stage 5's "highest earning multiplier" are unquantified.

### FR-8 Fraud Deterrence — Seven-Layer Framework (R1, R4)
Frictional deterrence: raise the cumulative cost of a successful fake review above its expected financial return.
1. Physical product photograph (cost of faking ≥ cost of the product).
2. Fuzzy word matching against a pre-seeded description/pattern database (plagiarism/AI-mirroring signal surfaced to the moderator; planned pathway to an NLP classifier).
3. Reverse image search + metadata analysis (creation date, device, geolocation inconsistencies) surfaced to the moderator.
4. IP address detection flagging multi-account submission/voting from one IP within defined windows.
5. Time-decayed Wilson Score visibility ranking with **velocity detection** (upvote surges flagged for admin review before ranking updates).
6. Community reporting: reasons (Fake proof, Plagiarized content, Spam, Harassment, Conflict of interest, Seller posing as buyer); escalation at **3+ independent reports or a single Stage 4+ report**; frivolous reporters' weight reduced.
7. Trust-weighted gate voting (*effective n*) rendering low-trust vote flooding structurally ineffective.

Plus **voter collusion detection**: pairwise upvote reciprocity rates, voter trust-stage distribution, and vote-spike indicators surfaced as informational flags on the earn_eligible review card (never auto-blocking).
- **[AMBIGUOUS]** Time windows, velocity thresholds, decay parameters, reciprocity thresholds, and the reverse-image-search provider are all unspecified.

### FR-9 Moderation & Administration (UC-07, UC-08, UC-09)
- Moderation queue with mod-facing signals; approve/reject with star-rating routing; confirmed violations ⇒ content removal, penalty, earning + vote-weight suspension, reporter notification; non-violations ⇒ restore + frivolous-report weight reduction; decision override on new evidence; escalation of coordinated abuse to the dev team via anomaly pattern reports.
- Platform administration: user/trust management, account suspension, commission CSV import & reconciliation (Shopee and Lazada exports), earnings breakdown (per review/cycle, filterable), payout processing, monthly Honesty Fund distribution, platform analytics, filterable audit log.

## 5. Non-Functional Requirements

| Area | Requirement (as specified) | International standard mapping |
|---|---|---|
| **Quality model** | All 8 ISO/IEC 25010:2011 characteristics; 40-item Likert instrument; Cronbach's α ≥ 0.70 | ✅ ISO/IEC 25010 explicitly adopted (2011 edition — see §2 note on the 2023 revision). Compatibility/Maintainability/Portability are measured via user-observable proxies — a methodological compromise, not full conformance assessment. |
| **Security** | SSL/TLS in transit; Redis-backed sessions; RBAC at API level; Supabase row-level security; layered fraud framework; security testing phase | ⚠️ **[GAP]** No ISO/IEC 27001 ISMS is referenced. Controls described are technical point controls; there is no stated risk-assessment process, policy set, incident-management procedure aligned to 27001/27002, or audit program. For a platform holding payout references, PII, and wallet balances, mapping existing controls to ISO/IEC 27001 Annex A (or at minimum a documented risk register) should be planned work. |
| **Privacy** | RA 10173 (Data Privacy Act of 2012) compliance; informed consent for participants; session-table PII retention (user agent purged at 90 days; IP hashed at 30, deleted at 90); revenue-split confidentiality; UREC ethical clearance | ⚠️ **Partial GDPR-equivalence.** RA 10173 broadly mirrors EU data-protection principles, and the spec operationalizes *storage limitation* (session PII schedule) and *purpose limitation* ("processed only for declared purposes"). **[GAP]** Not addressed: data-subject rights workflows (access, rectification, erasure, portability), a privacy notice, breach notification (NPC's 72-hour rule mirrors GDPR), Data Protection Officer designation, NPC registration, and cross-border transfer assessment (Supabase/PayPal/cloud hosting move personal data outside PH). These must be explicit before public launch. |
| **Accessibility** | Usability testing (clarity, badge legibility, navigation) across desktop and mobile browsers | ❌ **[GAP]** No accessibility standard is referenced. WCAG 2.1/2.2 conformance (recommend Level AA) is absent — no requirements for keyboard navigation, contrast, screen-reader semantics, alt text for proof images, or accessible form errors. Given the stated audience includes "older adults," WCAG alignment should be an explicit NFR. |
| **Performance** | "Responds within acceptable time thresholds"; simulated load testing before evaluation; CDN for static assets; load balancer; Redis caching | ⚠️ **[GAP]** No quantitative targets (p95 latency, throughput, concurrency, uptime SLO). "Acceptable" is undefined; ISO/IEC 25010 *performance efficiency* will be measured only via Likert perception items. |
| **Compatibility** | Chrome 90+, Firefox 88+, Safari 14+, Edge 90+; Windows 10 / macOS 11 / Android 10 / iOS 14 minimum; responsive Next.js + Tailwind UI; min device i3/Ryzen 3, 4 GB RAM, 5 Mbps | Maps to ISO/IEC 25010 *compatibility/portability*; a concrete matrix is provided. |
| **Reliability / DR** | Supabase automated daily backups with point-in-time recovery; media in Supabase Storage with access policies; verification assets replicated across availability zones; documented restore procedure | ⚠️ **[GAP]** No RTO/RPO targets; no ISO 22301/27031 continuity mapping — likely acceptable for the evaluation phase, should be quantified before launch. |
| **API conventions** | Internal service communication via RESTful APIs over HTTPS | ⚠️ Partially aligned. FastAPI auto-generates an **OpenAPI** description, but the spec never commits to publishing/maintaining an OpenAPI contract, versioning policy, or error-format convention (e.g., RFC 9457 problem details). Recommend making the OpenAPI document a governed artifact. **[GAP]** |
| **Localization** | Content in Filipino, English, Taglish; `language` enum on users and reviews | **[AMBIGUOUS]** Whether the *UI itself* is localized (vs. user content only) is unspecified; no i18n framework or translation workflow is named. |
| **Payments** | PayPal payouts only | PCI DSS scope is effectively delegated to PayPal (no card data stored). Note that `users.payment_account` stores payout account identifiers — treat as sensitive personal data under RA 10173 / GDPR-equivalent principles. |

## 6. Assumptions & Constraints

- **Legal/ToS constraint:** Shopee and Lazada ToS **prohibit automated data extraction** — hence manual product canonicalization, community-sourced pricing only, manual affiliate link generation, and manual commission CSV import. All automation on this path is blocked pending a formal API partnership / data-sharing agreement.
- **Regulatory constraints:** RA 10173 (privacy); RA 11967 Internet Transactions Act (governs the planned GCash/Maya integrations — business permit + BIR + DTI registration required); RA 7394 Consumer Act (framing). The Philippines has **no FTC-style fake-review rule** — the platform's design is itself the enforcement mechanism. The closest international analogs are the US FTC Consumer Reviews Rule (2024) and OECD e-commerce consumer-protection guidance (both cited in the spec); no formal conformance is claimed to either.
- **Operational constraint:** Manual moderation by a **single platform administrator** is the primary review mechanism — explicitly documented as a launch-state implementation that does not scale.
- **Evaluation constraints:** Two-month window; convenience sampling (acknowledged representativeness limit); the evaluation coincides with the **Seeding Phase**, so all observed earn_eligible outcomes reflect moderator judgment, not the Wilson threshold; UREC ethical clearance required before data collection.
- **Financial assumption:** Shopee Affiliate Program rates (3–10%) and continued account standing; the earning model depends on a third-party affiliate program the platform does not control.
- **Statistical assumption:** ~15% voting participation rate (basis for the 50-reviewer Seeding threshold: LB 0.65 @ 95% needs ~8 effective votes at 90% positive ⇒ ~53 ⇒ rounded to 50 active Stage 2+ voters).

## 7. Out-of-Scope Items (current build)

- Automated scraping or API-based ingestion of Shopee/Lazada listing, price, or commission data (ToS-blocked).
- Automated product name standardization (NLP) — planned, blocked on API partnership.
- NLP-based fake/AI-review classifier and AI-assisted moderation pre-screening — planned future development (also constrained by regulatory/technical requirements for AI moderation in a financial-incentive context).
- Automated trust-progression score updates (partial automation is planned future work).
- GCash and Maya payouts — planned, blocked on business permit / BIR / DTI registration (RA 11967).
- Product categories beyond the pilot seeding focus (electronics & accessories: power banks, Bluetooth earphones, portable fans, USB accessories) — organic expansion is a design intent, not an evaluation-period deliverable.
- Native mobile apps (web-only; responsive design).
- Seller-side verification beyond store-name cross-checks.

## 8. Open Ambiguities Register (do not build on guesses)

| # | Item | Why it matters |
|---|---|---|
| A1 | Trust score percentage / `reputation_score` formula undefined | Directly multiplies gate vote weights; core to earn_eligible integrity |
| A2 | Velocity-detection thresholds, time windows, and time-decay parameters unspecified | Rankings and fraud flags are unimplementable without them |
| A3 | Reverse-image-search and plagiarism-check providers/implementations unnamed | Cost, latency, and privacy implications differ hugely by choice |
| A4 | `verification_tier` (default `tier_0`) and `member_type` enums have no defined tiers | Schema implies a tiering model the narrative never describes |
| A5 | `earn_eligible` flag exists on the **answers** table, but Q&A earning is never described in the text | Feature scope unclear — are answer earnings in or out? |
| A6 | Affiliate links generated via the **Shopee** Affiliate account, but commission CSVs are imported from **Shopee and Lazada** | Is there a Lazada affiliate relationship? Attribution model incomplete |
| A7 | Cloud provider unchosen ("AWS, GCP, or Azure") | Blocks infra work, cost model, and data-residency analysis |
| A8 | Q&A "relevant product experience" routing logic undefined | Notification/matching behavior unimplementable as written |
| A9 | Stage 4 "relaxed proof requirements" and Stage 5 "highest earning multiplier" unquantified | Incentive math incomplete |
| A10 | No quantitative performance/uptime targets | NFR verification impossible beyond user perception |
