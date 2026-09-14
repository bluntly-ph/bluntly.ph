# Bluntly.ph — Full Feature Acceptance Matrix

Every feature of the product contract, with its backend, frontend, admin, test
and production status, the blocker if it has one, and the evidence the status
rests on. **Zero rows may be unclassified.**

## Provenance — read this before trusting a row

Two sources define the functional contract, and this matrix is built from both:

1. **`docs/01-bluntly-ph-PRD.md` §4, FR-1…FR-9** — the functional requirements
   in the repository, derived from the Problem–Requirements Matrix (R1–R6) and
   use cases UC-01…UC-09.
2. **The owner's completion contract** (session instruction, 2026-09-13), which
   enumerates the same product and in places extends or reverses the PRD.

**The owner's "Full Features List" document itself has not been supplied to
this session.** Where the two sources above disagree, the disagreement is
recorded in the row rather than resolved silently — see *Contract conflicts*
below. If the Full Features List contains an item absent from both sources, it
is not in this matrix and cannot be, so that document should be checked
against this one.

The reference screenshot pack remains the **visual** contract only. Where a
frame omits functionality the functional contract requires, the functionality
stays and the row is marked **INTENTIONAL PRODUCT DIFFERENCE**.

## Status vocabulary

| Status | Meaning |
|---|---|
| COMPLETE | Implemented, tested, and verified working in production |
| PARTIAL | Implemented in part; the gap is named in the row |
| MISSING | Not implemented |
| BLOCKED | Cannot proceed; the exact reason is named |
| N/A | The contract itself says it is out of scope, with the citation |

**PROVISIONAL** on a status means the code exists and is inventoried but the
end-to-end production verification the contract requires has not yet been run
for that feature. It is not a claim of completeness.

Last reconciled: **2026-09-13**, against `7f689db` (main) with `a254146` as the
last fully CI-green application SHA.

---

## FR-1 Account & Profile Management

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Email registration + verification | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `routes/auth.py`, `models/otp.py`, `test_auth`, `test_otp_api` |
| 1.2 | Login / session auth | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `services/auth_service.py`, `models/session.py`, `test_auth` |
| 1.3 | Profile management | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `routes/users.py`, `app/profile`, `test_username`, `test_avatar` |
| 1.4 | Roles + RBAC at API level | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `models/enums.py` (user/seller/moderator), `test_trust_boundaries` |
| 1.5 | Language preference en/fil/tl-x-taglish | PARTIAL | MISSING | — | MISSING | MISSING | — | enum exists on users; no UI selector, no i18n framework |
| 1.6 | **Notifications** (generation, persistence, unread/read, mark-as-read) | MISSING | MISSING | MISSING | MISSING | MISSING | — | no `models/notification.py`, no route, no surface |
| 1.7 | **User-to-user messaging** | MISSING | MISSING | MISSING | MISSING | MISSING | — | no model/route/service; contract §21 |

## FR-2 Product Discovery & Consolidation

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Keyword search, filters, sorting | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `routes/products.py`, `app/search`, `test_product_search_ranking` |
| 2.2 | Category browsing | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `app/categories`, `test_categories` |
| 2.3 | Product pages with verified reviews + badges | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `app/reviews/[id]`, `test_reviews_api` |
| 2.4 | Price observations (submit, pending/approved/rejected) | COMPLETE | COMPLETE | COMPLETE | PARTIAL | MISSING | — | Off-production (QA freeze): 0044 status/source/review_id; `/admin/price-observations` + `/moderate/prices`; self-decision 422, second decision 409. "Let's talk money" files a pending observation when a marketplace is picked (`price-capture-model.test.mjs`); "Report what you paid" under the price panel on `/reviews/[id]` (amount, marketplace, Manila-dated, optional variant — `price-report-model.test.mjs`). DB tests written, run in CI |
| 2.5 | **Price History panel** (≥3 independent **approved** observations) | COMPLETE | COMPLETE | — | COMPLETE | PARTIAL | — | **Correction:** this row said "no frontend panel anywhere"; `components/product/PricePanel.tsx` has rendered it on `/reviews/[id]` and in `ReviewAside` all along. `a6183cb` makes it count approved rows only and say when reports are waiting (`test_price_panel_rule`, 4 new cases). Production has the panel without moderation until 0044 ships |
| 2.6 | Product comparison | PARTIAL | PARTIAL | — | PARTIAL | PROVISIONAL | — | `app/compare`, `test_price_and_compare`; needs audit against "verified review scores + seller ratings + price data" — seller ratings do not currently exist |
| 2.7 | Product URL submission (Shopee/Lazada) | PARTIAL | PARTIAL | — | PARTIAL | PROVISIONAL | — | composer has a `sourceUrl` input; `test_url_schemes` |
| 2.8 | Duplicate detection / existing-product matching | COMPLETE | COMPLETE | PARTIAL | PARTIAL | MISSING | — | Off-production: `services/product_matching.py`; `POST /products` returns the existing product with 200 for the same listing link without tracking parameters, or the same name once case, spacing and punctuation are set aside. Exact keys only — near-matches stay a moderator's call; rejected submissions never match. The pickers already use the returned product. Admin PARTIAL: no merge tool for duplicates created before this. `test_product_matching_rules`; DB tests in CI. Thirteen fixed-name product fixtures (nine call sites, four helpers) were given unique names or links so the cumulative CI database cannot fold them into earlier runs' products |
| 2.9 | Admin sets canonical product name | PARTIAL | — | PARTIAL | MISSING | PROVISIONAL | — | `moderate/products` exists; canonicalisation workflow not audited |
| 2.10 | Automated NLP name standardisation | N/A | N/A | N/A | N/A | N/A | Out of scope — PRD §7, blocked on a marketplace API partnership (ToS prohibits scraping) | PRD §6, §7 |

## FR-3 Review Submission

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Discussion (free-form) | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.discussion`; composer step 1 |
| 3.2 | Verdict + explanation | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.verdict`, `verdict_explanation`; step 2 |
| 3.3 | Star rating 1–5 | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.star_rating`; step 3 |
| 3.4 | Pros / cons (max 10 each) | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.pros/cons` JSONB; step 4 |
| 3.5 | **Target audience** | COMPLETE | COMPLETE | COMPLETE | PARTIAL | PENDING DEPLOY | — | `reviews.target_audience`; restored to step 5 in `b2f1e29`. **INTENTIONAL PRODUCT DIFFERENCE** — the frame draws no such field |
| 3.6 | Anti-target audience | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.anti_target_audience`; step 5 |
| 3.7 | Review title | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | 30-char client limit vs 200 in the API — intentional, see conflict C-4 |
| 3.8 | Product photograph ⇒ verified | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | `reviews.photo_url`, `verification_status`; step 6 |
| 3.9 | **Receipt / order screenshot** | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PENDING DEPLOY | — | `reviews.receipt_key`, `test_receipt_privacy`; restored to step 6 in `b2f1e29`. **INTENTIONAL PRODUCT DIFFERENCE** |
| 3.10 | Price-paid capture | COMPLETE | COMPLETE | — | COMPLETE | COMPLETE | — | `reviews.price_paid`; the "Let's talk money" card. Feeds 2.4 |
| 3.11 | Post-submission completion state | COMPLETE | COMPLETE | — | MISSING | PENDING DEPLOY | — | truthful wording landed in `468627c`; see conflict C-1 |
| 3.12 | Rejection notifications with reason + resubmit | PARTIAL | MISSING | PARTIAL | MISSING | MISSING | Depends on 1.6 | moderation records a reason; no delivery surface |
| 3.13 | Draft persistence across the 7 steps | COMPLETE | COMPLETE | — | COMPLETE | COMPLETE | — | `bluntly:review-drafts:v2`; `composer-gate-model.test.mjs` |

## FR-4 Seller Reviews & Seller Accounts

Built as M2 slice 4, then **withdrawn from contract on 2026-07-28** (migration
0024 dropped `users.seller_aggregates` / `seller_trust_score`; see
`docs/DEVIATIONS.md` §37–38 and the note in `models/user.py`). The owner's
completion contract §5–§6 **reinstates it**. Schema and API have landed
(`ef34e72`, `cb0ed79`, `94d4fd3`), with one deliberate change of shape: sellers
are their own rows rather than users, so unclaimed stores can exist. Frontend,
moderator console screen and deployment are still to come.

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Seller entity / profile | COMPLETE | COMPLETE | — | PARTIAL | MISSING | — | `models/seller.py`, 0042; `/sellers/[id]` (claim status, rating card, reviews). DB tests in CI; route-table tests local; build passes. Not deployed: production needs 0042/0043 applied first |
| 4.2 | Seller registration | COMPLETE | COMPLETE | — | PARTIAL | MISSING | — | `POST /sellers` find-or-create, deduplicated by normalised name + marketplace; "Add a seller" in `/sellers/rate`. A seller *account* is reached through an approved claim (4.3), not a separate signup |
| 4.3 | Claimed / unclaimed profiles + claim workflow | COMPLETE | COMPLETE | COMPLETE | PARTIAL | MISSING | — | `ClaimSellerForm` on the store page; `/moderate/sellers` queue with evidence, two-step approve, reject with note. Self-decision 422, claimant 403, late claim 409 — `test_sellers_api` (CI) |
| 4.4 | Seller review — accuracy (binary) | COMPLETE | COMPLETE | — | COMPLETE | MISSING | **Verified-buyer link not representable** | `SellerReviewCreate`, `seller-model.test.mjs`. FR-4 says seller reviews are "linked to verified transactions"; nothing links a seller to a purchase, so any onboarded account can rate a store |
| 4.5 | Seller review — order completeness (binary) | COMPLETE | COMPLETE | — | COMPLETE | MISSING | Verified-buyer link not representable — see 4.4 | "Exact order / Missing item" in the composer; `false` counts as an answer (tested) |
| 4.6 | Seller review — service responsiveness (1–5) | COMPLETE | COMPLETE | — | COMPLETE | MISSING | Verified-buyer link not representable — see 4.4 | CHECK constraint in 0042, Field(ge=1, le=5), 1–5 circles in the composer |
| 4.7 | Seller review — packaging quality (1–5) | COMPLETE | COMPLETE | — | COMPLETE | MISSING | Verified-buyer link not representable — see 4.4 | as 4.6 |
| 4.8 | Seller review — overall rating + would-recommend | COMPLETE | COMPLETE | — | COMPLETE | MISSING | Verified-buyer link not representable — see 4.4 | stars + recommend cards; title (30 UI / 200 API), prose ≥15, up to 4 owned photos (0043, `photo_not_owned`) |
| 4.9 | One seller review per (seller, reviewer) | COMPLETE | COMPLETE | — | PARTIAL | MISSING | — | `uq_seller_review_once` + 409 `seller_review_exists`, surfaced by the composer. DB test in CI |
| 4.10 | Seller dashboard (aggregates, trends, volume, Q&A) | COMPLETE | COMPLETE | — | PARTIAL | MISSING | — | Off-production: `GET /sellers/mine`, `GET /sellers/{id}/dashboard` (approved owner only, `not_store_owner` 403); `/sellers/[id]/dashboard`: rating card, reviews per Manila month (zero-filled, 6 months), store questions still waiting on the store. "Trends" are shown as counts per month, not arrows or percentages the volume cannot support. `test_seller_dashboard_rules`, `seller-dashboard-model.test.mjs`; DB tests in CI |
| 4.11 | Seller responds to seller-directed Q&A | COMPLETE | COMPLETE | PARTIAL | PARTIAL | MISSING | — | Off-production: 0045 `questions.seller_id`, `answers.is_seller_answer`; store page Questions section + ask form; question page shows the store's answer under its name with Claimed Profile. Only an approved owner answers as the store; no First Responder badge for it (`test_seller_questions_rules`, DB tests in CI). Admin PARTIAL: the moderator Q&A tab names the store but has no store filter. Product questions directed at "the seller" still have no store to route to |
| 4.12 | Public seller rating summary | COMPLETE | COMPLETE | — | COMPLETE | MISSING | — | `summarize_reviews` + `rating_distribution`; `SellerRatingSummary` omits rates for an unrated store; `overall_average` in search |
| 4.13 | Action Menu "Rate a Seller" state | N/A | COMPLETE | — | COMPLETE | MISSING | — | Enabled → `/sellers/rate` now that 4.4–4.8 exist; `action-menu-model.test.mjs` |
| 4.14 | Seller verification by store-name cross-check | COMPLETE | COMPLETE | COMPLETE | PARTIAL | MISSING | — | The moderator decision is FR-4's check: `/moderate/sellers` shows the claimant's evidence beside a link to the store page, which links the public listing |
| 4.15 | Seller Sellers tab on /search | COMPLETE | COMPLETE | — | COMPLETE | MISSING | — | `GET /sellers?q=`, `SellerResultRow`, `search-tabs.test.mjs` |
| 4.16 | Seller review moderation (removal) | COMPLETE | COMPLETE | COMPLETE | PARTIAL | MISSING | — | Seller reviews publish without the product gate; `POST /admin/seller-reviews/{id}/removal` (0043), moderator control on the store page; removed rows leave list, summary and count (CI test) |

## FR-5 Community Q&A

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Buyer asks a question | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `models/qa.py`, `routes/qa.py`, `app/questions/new` |
| 5.2 | Audience selection (buyers vs seller) | COMPLETE | COMPLETE | — | PARTIAL | PROVISIONAL | Delivery to a seller depends on 4.1 | `QuestionDirectedTo.buyers/seller`, `AskQuestionForm.tsx`; the choice is stored and shown, but with no seller entity there is nobody to route it to |
| 5.3 | Registered-user answers | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `services/qa_service.py`, `QaAnswersTab` |
| 5.4 | Seller answers where claimed | COMPLETE | COMPLETE | PARTIAL | PARTIAL | MISSING | — | See 4.11: store questions only. `is_seller_answer` requires `claim_status == claimed` and the approved owner |
| 5.5 | Best Answer (one per question) | COMPLETE | COMPLETE | COMPLETE | PARTIAL | PROVISIONAL | — | `qa_service.mark_best_answer` (demotes the previous one), `questions.best_answer_id`, `answers.is_best_answer`; rendered on `/questions/[id]` and in `QaAnswersTab` |
| 5.6 | First Responder badge (first answer < 24h) | COMPLETE | COMPLETE | COMPLETE | PARTIAL | PROVISIONAL | — | `FIRST_RESPONDER_WINDOW = 24h` in `qa_service`, awards the `first_responder` badge, refuses self-answers; `answers.is_first_responder` rendered on `/questions/[id]` |
| 5.7 | Answer voting | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `models/vote.py`, `test_votes_api` |
| 5.8 | Answers ranked by time-decayed Wilson | COMPLETE | PARTIAL | — | COMPLETE | PROVISIONAL | — | `services/ranking.py`, `test_ranking_properties` |
| 5.9 | earn_eligible gate for eligible answers | COMPLETE | — | PARTIAL | COMPLETE | PROVISIONAL | — | `answers.earn_eligible`, `answers.wilson_score`; `test_qa_self_dealing` |
| 5.10 | Question search | COMPLETE | COMPLETE | — | COMPLETE | COMPLETE | — | `test_question_search` |
| 5.11 | "Relevant product experience" routing | BLOCKED | BLOCKED | — | — | — | **PRODUCT_DECISION_REQUIRED** — PRD FR-5 marks the matching logic `[AMBIGUOUS]`: who counts as relevant, and how they are notified, is unspecified | PRD §4 FR-5 |

## FR-6 Incentives, earn_eligible & Payouts

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Publication ≠ earning eligibility | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `earn_eligible_status`, `test_affiliate_transitions` |
| 6.2 | Manual moderator gate | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `moderate/review-queue`, `test_affiliate_status` |
| 6.3 | Affiliate link generation + attachment | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `moderate/affiliate-links`, `services/referral_service.py` |
| 6.4 | Review attribution / redirect | COMPLETE | COMPLETE | — | COMPLETE | PROVISIONAL | — | `routes/redirect.py`, `routes/postback.py`, `test_referral_api` |
| 6.5 | Answer attribution | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | needs audit |
| 6.6 | Commission tracking | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `models/commission.py`, `test_commissions_api` |
| 6.7 | CSV import / reconciliation (Shopee + Lazada) | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `services/affiliate_ingest.py`, `report_formats.py`, `test_affiliate_ingest` |
| 6.8 | 40 / 30 / 30 split | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `test_split_properties` |
| 6.9 | Split confidentiality (reviewer sees own only) | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `test_earnings` |
| 6.10 | Seeding vs post-seeding gate phases | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | needs audit against the 0.65 @ 95% + 3 Stage-2 voters rule |
| 6.11 | Honesty Fund ledger + monthly distribution | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | See 6.12 | `models/honesty_fund.py`, `moderate/honesty-fund`, `test_retention_and_fund` |
| 6.12 | Honesty Fund **calculation policy** | BLOCKED | BLOCKED | BLOCKED | — | — | **PRODUCT_DECISION_REQUIRED — HONESTY FUND FORMULA.** See conflict C-2: the PRD *does* state a formula, but it depends on a trust-score percentage the PRD itself marks `[AMBIGUOUS]` with no computation defined | PRD FR-6, FR-7 |
| 6.13 | Earnings dashboard | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `app/dashboard`, `services/earnings.py` |
| 6.14 | Wallet + ₱300 payout threshold | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `models/payout.py`, `test_payouts_api`, `test_wallet_concurrency` |
| 6.15 | Payout processing (simulated) | PARTIAL | PARTIAL | PARTIAL | COMPLETE | PROVISIONAL | See conflict C-3 (PayPal vs GCash/Maya) | `services/payout_service.py`, `test_scheduler_financial_safety` |

## FR-7 Trust Progression

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 7.1 | Six stages Newcomer…Community Expert | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `services/trust.py`, `trust_service.py`, `test_trust`, `TrustBadge` |
| 7.2 | Stage thresholds (counts, helpfulness, duration) | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `test_trust`, `test_trust_api` |
| 7.3 | Vote-weight multipliers per stage | COMPLETE | — | — | COMPLETE | PROVISIONAL | — | `test_trust_boundaries` |
| 7.4 | <30-day accounts: weight halved | COMPLETE | — | — | COMPLETE | PROVISIONAL | — | `test_trust_boundaries` |
| 7.5 | Probation ⇒ gate vote weight 0 | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `users.is_on_probation` |
| 7.6 | Strikes | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `users.strikes` |
| 7.7 | Best Answer count feeding Stage 4 | PARTIAL | — | — | PARTIAL | PROVISIONAL | Depends on 5.5 | — |
| 7.8 | Frontend trust display matches computed state | PARTIAL | PARTIAL | — | MISSING | MISSING | — | contract §9 requires an audit for decorative trust levels; not yet done |
| 7.9 | `reputation_score` computation formula | BLOCKED | — | — | — | — | **PRODUCT_DECISION_REQUIRED** — PRD FR-7 marks the trust-score percentage `[AMBIGUOUS]`, no formula defined; Stage 4 "relaxed proof" and Stage 5 "highest multiplier" unquantified | PRD §4 FR-7 |

## FR-8 Fraud Deterrence (seven layers)

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 8.1 | L1 Physical product photograph | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | — | see 3.8 |
| 8.2 | L2 Plagiarism / fuzzy word matching | MISSING | — | MISSING | MISSING | MISSING | — | no provider interface, no status field, no moderator signal |
| 8.3 | L3 Reverse image search + metadata | MISSING | — | MISSING | MISSING | MISSING | Provider unnamed in the PRD (`[AMBIGUOUS]`); the interface and status tracking are still implementable without one | PRD FR-8 |
| 8.4 | L4 IP multi-account detection | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | — | `services/fraud_service.py`, `test_fraud_signals` |
| 8.5 | L5 Time-decayed Wilson + velocity detection | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | Thresholds `[AMBIGUOUS]` in the PRD | `services/ranking.py`, `test_ranking_properties` |
| 8.6 | L6 Community reporting + escalation | COMPLETE | COMPLETE | COMPLETE | COMPLETE | PROVISIONAL | — | `routes/admin_reports.py`, `test_reports_api` |
| 8.7 | L7 Trust-weighted gate voting (effective n) | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `test_trust_boundaries`, `test_split_properties` |
| 8.8 | Voter collusion signals (reciprocity, spikes) | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | Thresholds `[AMBIGUOUS]` | `test_fraud_signals` |
| 8.9 | Geographic vote aggregation + ranked locations | COMPLETE | — | COMPLETE | COMPLETE | COMPLETE | — | `services/request_traffic_service.py`, `moderate/analytics`, `test_request_distribution` |
| 8.10 | Flagged voters, High/Low trust segmentation, risk levels | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | contract §18 names five risk levels; not yet audited against implementation |

## FR-9 Moderation & Administration

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| 9.1 | Queue categories Review / Answer / Report / Support | COMPLETE | — | COMPLETE | COMPLETE | COMPLETE | — | `ReviewQueueScreen.tsx`; verified live, 4 tabs, 0 dead controls |
| 9.2 | Queue states In Review / Archive | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | needs audit |
| 9.3 | Priority score + ordering contract | COMPLETE | — | COMPLETE | COMPLETE | COMPLETE | — | `services/moderation_priority.py`, `test_moderation_priority` |
| 9.4 | Queue item data (product, author, trust, receipt status, age) | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | reverse-image status blocked by 8.3 |
| 9.5 | Reviewer snapshot (account age, trust score, review counts) | PARTIAL | — | PARTIAL | MISSING | PROVISIONAL | — | contract §17 |
| 9.6 | Engagement signals (upvotes, views, shares, reports, comments) | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | `reading_telemetry` provides views |
| 9.7 | Inline report surfacing (category, description, history) | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | — | contract §19; `test_reports_api` |
| 9.8 | Approve/reject with star-rating routing | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `test_affiliate_transitions` |
| 9.9 | Penalties, suspension, vote-weight suspension | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `routes/admin_users.py`, `test_admin_user_management` |
| 9.10 | Audit log (filterable) | PARTIAL | — | PARTIAL | PARTIAL | PROVISIONAL | — | `moderate/activity` |
| 9.11 | Platform analytics | COMPLETE | — | COMPLETE | COMPLETE | PROVISIONAL | — | `routes/admin_analytics.py`, `test_admin_overview` |
| 9.12 | **Date column clipped at 1280** | — | DEFECT | DEFECT | COMPLETE | DEFECT | — | `.final-checks.mjs`; pane 533 vs table min 544 at `xl`; see the fix candidate in `.bluntly-autopilot/COMPOSER-1TO1.md` |

## Contract items outside FR-1…FR-9

| # | Feature | Backend | Frontend | Admin | Test | Production | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| X.1 | **Disclosure of material relationship** | COMPLETE | COMPLETE | COMPLETE | COMPLETE | MISSING | — | Off-production: 0046 `reviews.material_relationship` (none / free_or_discounted / connected; NULL = never asked, not defaulted); versioned with every edit. Composer step 7 asks it and Submit waits — **INTENTIONAL PRODUCT DIFFERENCE**, the frame draws the title only. The review page shows a declared relationship beside "Verified purchase"; the moderation queue card and the review-queue detail panel show it (a pre-question review reads "Not asked"). `test_material_relationship_rules`, `disclosure-model.test.mjs`, `composer-gate-model.test.mjs`; DB tests in CI. Contract §13 |
| X.2 | **Trust badge gated on real verification state** | COMPLETE | PARTIAL | — | PARTIAL | PROVISIONAL | — | `verification_status` drives it; needs the §15 audit that it is never awarded on trust level or photo presence alone |
| X.3 | **3D / 360 product experience** | MISSING | MISSING | MISSING | MISSING | MISSING | — | contract §20; not in the PRD. No asset metadata, no viewer, no honest-unavailable state |
| X.4 | **Simulated GCash / Maya payout flow** | MISSING | MISSING | MISSING | MISSING | MISSING | See conflict C-3 | contract §16 |
| X.5 | Supabase backup / PITR configuration | UNVERIFIED | — | — | — | UNVERIFIED | Needs platform-console inspection, not code | contract §24 |
| X.6 | Supabase Storage access control on verification assets | COMPLETE | — | — | COMPLETE | PROVISIONAL | — | `services/storage.py`, `test_receipt_privacy` |
| X.7 | Session auth / API RBAC / TLS | COMPLETE | — | — | COMPLETE | PROVISIONAL | — | see 1.2, 1.4 |
| X.8 | RA 10173 technical privacy controls | PARTIAL | — | PARTIAL | COMPLETE | PROVISIONAL | Legal conformance is not a code claim — PRD §5 lists the policy gaps | `services/pii.py`, `test_pii_retention` |
| X.9 | Body typeface audit across reference families | — | PARTIAL | — | — | PARTIAL | — | applied in the composer only; contract §28 forbids a blind app-wide roll |
| X.10 | Step 7 preview shows no fabricated metrics | — | COMPLETE | — | — | COMPLETE | — | **INTENTIONAL PRODUCT DIFFERENCE**; contract §26 |

## Explicitly not built (design-only prototype rows, contract §30)

| Item | Status | Reason |
|---|---|---|
| Bookmarks | N/A | Not in the PRD or the completion contract; one prototype row is not a product requirement |
| Block reviewer | N/A | Same |
| "Get notified about this review" | N/A | Generic notification infrastructure is required (1.6); this specific affordance is not |
| TikTok Shop attribution | N/A | Affiliate infrastructure is required (6.3–6.7); this marketplace is not supported and inventing it would fabricate attribution |
| Footer social accounts | N/A | No accounts exist to link |

## Contract conflicts — recorded, not silently resolved

**C-1 — Publication timing.** PRD FR-3 says reviews *"publish immediately"*.
The implementation holds every review for moderation, and the completion
contract §25 assumes that gate. Resolution taken: the moderation gate stands
(precedence rule 2, accepted moderation requirement) and the completion screen
was made truthful in `468627c`. **The PRD sentence is now stale and should be
corrected.**

**C-2 — Honesty Fund formula.** The completion contract §22 says *"NO FORMULA
EXISTS YET — DO NOT INVENT"*. The PRD FR-6 **does** state one: pool = 30% of
cycle commissions, payout = (review Honesty Score ÷ total eligible Honesty
Scores) × pool, Honesty Score = trust-weighted helpfulness × price bracket
(1.0/1.5/2.0). It is not computable because *trust-weighted* depends on the
`reputation_score` percentage the PRD itself marks `[AMBIGUOUS]` (7.9). So the
plumbing is buildable and the final distribution is not. Classified BLOCKED on
the policy only.

**C-3 — Payout rails.** PRD FR-6 and §7: PayPal only; GCash/Maya explicitly out
of scope pending business permit, BIR and DTI registration under RA 11967. The
completion contract §16 asks for *simulated* GCash/Maya. Simulation carries no
regulatory exposure, so X.4 is planned as a deterministic simulated status flow
with no real transfer. **Worth the owner confirming**, since the PRD treats
these rails as blocked rather than simulated.

**C-4 — Title length.** Reference pack: 30 characters. API: 1–200. Contract §27
says keep 30 on the client and leave the API permissive. Implemented that way;
tests should pin both so the difference stays intentional.

**C-5 — Seller features: descoped, then required.** The owner descoped FR-4 on
2026-07-28 (reaffirmed 2026-08-07) and 0024 dropped `seller_reviews`; the
console rail, the search tabs and the action menu all said so. The completion
contract lists seller review, claimed/unclaimed profiles, moderated claims and
review monitoring as P1 required. Resolution taken: the later, explicit
instruction wins. FR-4 was rebuilt in a different shape (sellers are their own
rows, so an unclaimed store is representable; claims are moderator-approved
only), and the tests that pinned the descope were changed to pin the
reinstatement. Seller reviews still publish without the product gate, as
DEVIATIONS §37 always said, with moderator removal as the check.

---

## QA-001 .. QA-012, re-run 2026-09-13

Re-run from scratch against production by `.qa-matrix.mjs`, not carried over
from `docs/RELEASE_HANDOFF.md`. **All twelve pass.** This is my own harness,
not an independent sign-off.

The first run had six failures. One was a product defect and five were the
harness measuring the wrong thing:

| Case | First run | Diagnosis |
|---|---|---|
| QA-012 | non-pointer control | **PRODUCT DEFECT** — the landing hero's search submit rendered `cursor: default`. Twelve hand-rolled buttons did. Fixed in `a295509` as one base-layer rule |
| QA-001 | "0/2 cards mention fan" | harness — the hit *is* relevant ("Jisulife Life9" is a handheld fan) and one of the two "results" was the Write-a-review CTA |
| QA-003 | no drafts listed | harness — `readDrafts()` parses `Record<slot, Draft>`; the harness wrote an array |
| QA-009 | no activedescendant | harness — `/search` has two visible comboboxes; it filled one and inspected the other |
| QA-011 | "saw 4k" | harness — the 4k is prose, *"a sub-P4k board"*, not a vote total |
| QA-012 | nested button | already fixed in `ceb4cb9` — five more sites carried the pattern QA-012 named |

## Corrections applied after first publication

Row-by-row verification found the first pass had **understated FR-5**. It was
written from a model/route/service inventory, and four rows were wrong:

| Row | First pass | Verified | How it was found |
|---|---|---|---|
| 5.2 | PARTIAL / MISSING test | `QuestionDirectedTo` is a real enum, stored and rendered | read `AskQuestionForm.tsx` |
| 5.5 | PARTIAL | `mark_best_answer` demotes the previous winner; rendered in three places | read `qa_service.py` |
| 5.6 | MISSING everywhere | 24h window, badge award, self-answer refused | read `qa_service.py` |
| 5.9 | PARTIAL backend | `answers.earn_eligible` and `wilson_score` both exist | read `models/qa.py` |

The lesson is recorded rather than quietly fixed: **a grep for a feature name
is not evidence of its absence.** Rows still marked MISSING below on the
strength of an inventory alone — 1.6, 1.7, 2.8, 8.2, 8.3, X.3 — were each
re-checked by reading the relevant service, not by counting matches.

## What this matrix says overall

- **Rows: 96. Unclassified: 0.**
- Largest genuine gaps, in contract priority order: seller reviews and seller
  accounts (FR-4 — schema and API landed; frontend, console screen and deployment
  still to come, and no verified-buyer link yet),
  notifications and messaging (1.6, 1.7), price-history frontend (2.5),
  duplicate detection (2.8), disclosure (X.1), plagiarism and reverse-image
  layers (8.2, 8.3), 3D/360 (X.3).
- Genuine blockers: 5.11, 6.12, 7.9 (policy undefined), X.5 (platform console),
  and 8.3's provider choice — everything else is engineering work.
