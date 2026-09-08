# Moderation Priority and Learning Foundation

**Date:** 2026-09-08

**Status:** Owner-approved design, pending implementation plan

**Scope:** Review moderation queue prioritization, decision capture, quality control, and future model-readiness

## 1. Objective

Build a scalable, explainable moderation queue that helps moderators address the most important work first and creates reliable evidence for later algorithm research.

This release does **not** create an autonomous authenticity judge. It creates:

- one canonical server-owned priority policy;
- truthful, global server-side ordering before pagination;
- persisted queue lifecycle and SLA facts;
- structured, auditable moderator outcomes;
- quality-control sampling and adjudication signals;
- a safe dataset boundary for future offline modelling.

Reader dwell time remains collection-only. It must not affect queue priority, authenticity, publication, vote weight, trust, funds, commissions, or payouts.

## 2. Current reality and problem statement

At `5c0602d7bdd341be6af46b51bff072280591e5c5`, priority has incompatible definitions:

- `components/admin/review-queue-model.ts` labels an item High if any velocity, collusion, or duplicate-content flag fires; Normal if it is unverified; otherwise Low.
- `backend/app/services/admin_overview_service.py` calls reported queued reviews high priority and urgent.
- `backend/app/services/referral_service.py` returns pending reviews oldest-first, but pagination occurs before fraud signals are evaluated.
- the UI then re-sorts only the fetched page, defaulting to newest-first.

Wilson score and author reputation are displayed as context. They are not a coherent moderation-priority policy and must not be silently reinterpreted as proof of authenticity or fraud.

The existing moderation audit log records actions, free-text notes, and optional JSON context, but it does not guarantee a policy version, assessment snapshot, structured outcome, moderator confidence, acted-on review version, or report-resolution linkage. Historical moderator decisions therefore are not yet reliable supervised-learning labels.

## 3. Governing principles

1. **Priority means attention, not guilt.** A report or anomaly moves an item earlier; it does not prove misconduct.
2. **One policy owns priority.** Backend queue, overview, filters, exports, and UI consume the same result.
3. **Global ordering precedes pagination.** Client-side sorting of the first 50 rows is not a scalable queue.
4. **Operational urgency and integrity concern stay separate.** Queue age/SLA and risk indicators are displayed and stored independently.
5. **Every priority is explainable.** A moderator can see the factors, observed values, contributions, and policy version.
6. **Signals remain advisory.** No priority evaluator may publish, reject, penalize, suspend, alter trust, change vote weight, or move money.
7. **Moderator decisions are observations, not automatic truth.** Only agreed second reviews, upheld appeals, or explicit adjudication may become validated labels.
8. **Sensitive data is minimized.** Assessment snapshots never include review text, receipt paths, email, staff reference, IP address, raw telemetry, or per-person location.
9. **Historical explanations are immutable.** Past decisions retain the assessment used at decision time even after the policy changes.
10. **Reading telemetry remains isolated.** Dwell, scroll, interaction timing, and reading-session identity are forbidden inputs in this phase.

## 4. Queue lifecycle model

Add an additive `moderation_queue_entries` table. Each row represents one queue episode rather than one content object forever.

Required fields:

- `id` UUID primary key;
- `target_type` and `target_ref`;
- `source`: `initial_review`, `post_publish_edit`, `community_report`, `manual_escalation`, or `quality_audit`;
- `status`: `open`, `claimed`, `resolved`, or `cancelled`;
- `lane`: `escalated`, `reported`, `integrity`, `routine`, or `quality_audit`;
- `queued_at`, `due_at`, `claimed_at`, `resolved_at` in UTC;
- optional `assigned_to` moderator UUID;
- `priority_policy_version`;
- `integrity_score` as a bounded integer from 0 to 100;
- `priority_band`: `high`, `normal`, or `low`;
- `assessment` JSONB containing the validated factor snapshot;
- timestamps.

Database invariants:

- at most one active non-quality-audit queue episode for a target/source family;
- resolved/cancelled entries have `resolved_at`;
- claimed entries have `assigned_to` and `claimed_at`;
- score remains within 0–100;
- `due_at >= queued_at`;
- target, status, lane, due time, and ordering columns are indexed;
- queue creation and the content state transition that caused it occur atomically.

Initial migration backfill creates one episode for each currently pending unpublished review and one for each qualifying post-publication edit. `queued_at` uses the best available existing event time and records `backfilled: true` in the assessment; the system must not pretend this is exact lifecycle history.

## 5. Canonical priority policy v1

Create a pure backend `moderation_priority` module. It exposes a single `POLICY_VERSION = "review-priority-v1"` and returns a `PriorityAssessment` with:

- version;
- lane;
- integrity score;
- priority band;
- ordered factor list;
- SLA state;
- deterministic order key.

Each factor contains a stable code, observed value, integer contribution, and plain-language explanation.

### 5.1 Integrity-attention factors

The v1 score is additive and capped at 100:

| Factor | Contribution |
|---|---:|
| Edited after monetization | 40 |
| Collusion advisory fired | 35 |
| Duplicate-content advisory fired | 30 |
| Vote-velocity advisory fired | 15 |
| One distinct report | 15 |
| Two or three distinct reports | 25 total |
| Four or more distinct reports | 35 total |
| Report reason: fake proof or harassment | +20 |
| Report reason: seller posing as buyer or plagiarized | +15 |
| Report reason: conflict of interest | +10 |
| Report reason: spam | +5 |
| Report reason: other | +0 |

Only the highest report-count bracket applies. Only the highest report-reason contribution applies, regardless of the number of reports. This prevents report brigading from growing the score without bound.

Wilson score, author reputation/trust stage, verification status, review length, star rating, engagement total, geography, dwell time, scroll depth, and interaction timing contribute **zero** in v1. They may be displayed as clearly labelled context where already authorized.

### 5.2 Lanes

Lanes are mutually exclusive operational routing, evaluated in this order:

1. `escalated` — explicit human escalation;
2. `reported` — one or more unresolved community reports;
3. `integrity` — post-monetization edit or any live integrity advisory;
4. `routine` — all other normal queue work;
5. `quality_audit` — separate second-review sampling of completed decisions, never mixed with suspicion lanes.

Reports affect attention but are never presented as verified wrongdoing.

### 5.3 SLA state

Initial SLA targets:

- escalated: 1 hour;
- reported: 4 hours;
- integrity: 8 hours;
- routine: 24 hours;
- quality audit: 72 hours.

The evaluator returns `on_track`, `approaching`, or `overdue`. Approaching begins after 75% of the target interval. SLA uses queue-episode age, not the review creation time.

### 5.4 Priority band and deterministic ordering

Band is a presentation summary:

- High: escalated, overdue, or integrity score at least 40;
- Normal: approaching SLA or integrity score 15–39;
- Low: score below 15 and SLA on track.

Global ordering uses:

1. lane rank;
2. overdue before approaching before on-track;
3. higher integrity score;
4. earlier due time;
5. earlier queue time;
6. queue-entry UUID as a stable final tie-breaker.

The server evaluates all eligible candidates, orders them, and only then applies cursor pagination. Offset pagination may remain temporarily for compatibility but must not be the long-term queue contract.

## 6. Server API contract

Evolve the admin queue response to include:

- cursor and truthful total counts by lane/band/SLA state;
- queue-entry identity and lifecycle timestamps;
- canonical assessment and explanations;
- unresolved distinct report count and grouped reason summary;
- current assignment state;
- content, author, receipt-presence, Wilson, and trust context already permitted to moderators.

Supported server-side filters:

- lane;
- band;
- SLA state;
- factor code;
- reported/unreported;
- verification status;
- assignee;
- review ID and privacy-permitted staff lookup;
- queue source.

URL search parameters are canonical and shareable. The frontend does not implement another priority evaluator.

## 7. Structured moderator decisions

Mutation endpoints accept a validated `ModerationDecisionRequest`:

- `outcome`: publish, approve, reject, unpublish, remove, restore, escalate, or no_action as allowed by the existing state machine;
- one primary `reason_code` from the existing moderation taxonomy;
- optional secondary reason codes;
- `confidence`: low, medium, or high;
- optional bounded plain-text notes;
- optional escalation destination/reason when outcome is escalate;
- queue-entry ID and acted-on review version.

Before mutation, the service snapshots the current queue assessment. The content transition, queue resolution, and append-only moderation log are committed in one transaction. The log `context` is validated as schema version 1 and includes:

- context schema version;
- priority policy version;
- queue-entry ID/source/lane;
- score, band, SLA state, and factor codes/contributions;
- acted-on review version;
- structured outcome/reason/confidence;
- unresolved report count and bounded related report IDs;
- previous and resulting content states.

It excludes raw content, PII, receipt storage information, secrets, and telemetry.

Original report logs remain append-only. Resolution is projected from the later decision context; allegations are not deleted or rewritten.

## 8. Quality-control and label integrity

Completed moderator decisions are not immediately training labels.

Five percent of eligible completed decisions enter a separate `quality_audit` lane. Selection is deterministic from `SHA-256(decision_log_id + UTC date + audit_policy_version)`, with the policy version, population definition, and selection digest recorded. The sampler never changes content state, trust, scores, or payouts.

The second reviewer cannot be the original decision maker. The audit result is:

- agree;
- disagree;
- escalate for adjudication.

A future research export may mark an outcome `validated` only when:

- two independent moderators agree;
- an adjudicator resolves a disagreement;
- or an appeal produces an upheld final outcome.

Reversals and disagreements remain in the dataset rather than being overwritten. This allows measurement of moderator consistency and prevents the model from learning every historical action as truth.

## 9. Moderator UI and responsive behavior

Preserve the approved Figma review-queue visual language and existing admin shell.

Desktop at 1280px and wider:

- split queue and detail composition;
- canonical band, lane, SLA clock, assignment, and factor explanations adjacent to the selected item;
- grouped community reports with human-readable reasons and safe evidence links;
- sticky decision footer with confirmation and structured reason/confidence controls;
- no automatic receipt fetch; receipt access remains deliberate, short-lived, and audited.

Tablet:

- single-column queue followed by selected detail;
- sticky decision actions remain reachable inside the content pane.

Phone at 393px and 320px:

- master-to-detail interaction rather than two compressed panes;
- 44px minimum action targets;
- no document-level horizontal overflow;
- only true lists and detail content scroll;
- state, filters, and selected item remain recoverable through URL parameters where appropriate.

The UI explicitly separates:

- **why this needs attention** — assessment factors;
- **how soon it needs attention** — SLA;
- **what the evidence says** — raw permitted signals and reports;
- **what the moderator decided** — structured outcome.

Wilson and trust remain context, not risk labels. Geographic visualizations remain aggregate and must never imply per-voter location tracking.

## 10. Analytics and future modelling boundary

Phase 1 implementation produces operational queue analytics and validated decision exports, not a model.

Permitted aggregate measures:

- backlog and age by lane;
- SLA breaches;
- decisions per moderator and outcome;
- time to decision;
- report-to-outcome rates;
- reason-code distribution;
- disagreement, reversal, appeal, and escalation rates;
- policy-factor prevalence;
- random-audit agreement rate.

No leaderboard may reward speed without quality context.

Future modelling follows these gates:

1. Freeze a versioned, de-identified dataset snapshot.
2. Separate chronological train, validation, and holdout periods.
3. Use only validated/adjudicated outcomes as primary labels; retain unvalidated decisions as a separate field.
4. Evaluate ranking quality, capacity-weighted recall, calibration, false-positive rates, reversals, drift, and subgroup disparities.
5. Run the candidate in shadow mode with no user-visible or financial effect.
6. Compare against the rule policy and human baseline over a meaningful Bluntly sample.
7. Require a separate owner-approved design before assisted ranking changes production ordering.
8. Require another explicit approval before any narrow automated action.

The first production model, if later approved, may recommend ordering and confidence only. It must not autonomously decide authenticity, publication, penalties, trust, or payouts.

## 11. Telemetry and privacy isolation

`review_reading_sessions` and `review_first_vote_geo_buckets` remain research-only under the existing 90-day retention and access controls.

Hard prohibitions for this implementation:

- no import or query of reading telemetry from priority, moderation-decision, queue, trust, Wilson, publication, or payout modules;
- no raw telemetry in moderator APIs or DOM;
- no per-voter geography;
- no durable voter relationship graph;
- no email, staff reference, IP, raw user agent, or receipt locator in priority snapshots or research exports;
- no public priority, staff-only identifier, moderator metadata, or decision history exposure.

The existing telemetry-isolation suite must be extended to cover every new decision and queue module.

## 12. Failure handling and concurrency

- Queue claim uses an atomic conditional update; two moderators cannot successfully claim the same open episode.
- Stale claims expire under an explicit lease policy without changing content state.
- A mutation with a stale review version returns conflict and requires the moderator to reload.
- If the audit write or queue resolution fails, the content mutation rolls back.
- If assessment recomputation fails, the prior persisted assessment remains visible and the item is marked assessment-stale; it is never silently dropped.
- Unknown future factor codes render as labelled unknown values rather than breaking the queue.
- Policy-version changes use explicit re-evaluation jobs with bounded batches and observable progress.
- No failure path may auto-approve, auto-reject, or move money.

## 13. Testing and acceptance

Backend tests must prove:

- exact contribution and cap for every v1 factor;
- report-volume and report-reason bounds;
- Wilson, trust, verification, geography, and telemetry contribute zero;
- lane precedence, SLA boundaries, band thresholds, and deterministic ties;
- global ordering before pagination;
- truthful totals and server filters;
- queue lifecycle, requeue timing, claim races, stale versions, and rollback;
- atomic decision/audit persistence and immutable historical snapshots;
- report resolution without report mutation;
- deterministic 5% audit selection and independent-reviewer constraint;
- moderator RBAC and unchanged Super Admin rules;
- strict telemetry and payout isolation.

Frontend tests must prove:

- response rendering does not recompute priority;
- reason labels and raw signals cannot be confused;
- canonical URL filters;
- decision validation, confirmation, success/error feedback, and stale-version recovery;
- loading, empty, stale-assessment, unavailable-data, and permission states;
- no receipt auto-fetch.

Authenticated production acceptance covers 1440, 1280, 1024, 768, 393, and 320 widths, keyboard/focus behavior, no document overflow, real server ordering, deterministic reversible QA decisions, audit evidence, moderator access, normal-user denial, public non-exposure, and relevant production logs.

## 14. Delivery slices

1. **Policy and contract:** pure evaluator, batch inputs, one canonical backend response, ordering before pagination, overview convergence, tests.
2. **Lifecycle persistence:** additive queue-entry migration, backfill, claims, SLA state, bounded policy re-evaluation.
3. **Structured decisions:** validated requests, atomic audit snapshots, report resolution projection, activity/history API.
4. **Figma moderator workflow:** explanations, filters, grouped reports, decision footer, responsive master/detail behavior.
5. **Quality audit and research export:** deterministic sampling, second review/adjudication, de-identified validated-label export.
6. **Release chain:** full local gates, isolated PostgreSQL CI, exact-SHA deployment, migration, authenticated acceptance, public non-exposure, logs, and QA handoff.

Each slice is independently testable. No model training or autonomous judgment is part of these slices.

## 15. Explicit non-goals

- autonomous authenticity decisions;
- automatic penalties, publication, removal, trust changes, or payouts;
- using dwell/scroll/reading telemetry in priority;
- per-voter location tracking;
- a persisted social graph;
- treating report count as proof;
- fabricating reverse-image, plagiarism, or voter-risk results where providers/data do not exist;
- redesigning unrelated public product surfaces.

## 16. Success condition

The foundation is successful when moderators see one truthful and explainable queue, every decision is auditable with its contemporaneous policy context, completed decisions can be quality-checked rather than blindly labelled, the queue scales beyond one client-side page, and existing scoring/payment/privacy behavior is unchanged.
