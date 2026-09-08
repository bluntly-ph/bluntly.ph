# Moderation Priority Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the conflicting client/report-only priority definitions with one explainable server-owned v1 policy that globally orders and filters the entire review queue before pagination.

**Architecture:** A pure `moderation_priority` module evaluates already-loaded facts and returns a typed assessment. The queue service batch-loads reports, evaluates every eligible review, sorts deterministically, filters, and then paginates; the admin overview and frontend consume that same assessment instead of implementing their own rules. Queue lifecycle persistence, structured decisions, and quality-audit sampling remain separate implementation plans after this contract is released.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL, Next.js App Router, TypeScript, Node test runner

**Spec:** `docs/superpowers/specs/2026-09-08-moderation-priority-and-learning-foundation-design.md`

## Global Constraints

- Priority means attention, not guilt; no evaluator path mutates content, trust, votes, funds, commissions, or payouts.
- `POLICY_VERSION` is exactly `review-priority-v1`.
- Reading time, scroll, interaction timing, geography, Wilson score, trust/reputation, verification status, star rating, review length, and engagement totals contribute zero in v1.
- `QueueSignals` retains its exact existing six-field contract because telemetry-isolation tests freeze it.
- Every assessment contains stable factor codes, observed values, contributions, and human-readable explanations.
- Global server ordering and filtering occur before pagination.
- Existing local-only files and `.bluntly-autopilot/` are never staged.
- No production schema change is part of this first slice.

---

### Task 1: Pure priority policy and exact factor tests

**Files:**
- Create: `backend/app/services/moderation_priority.py`
- Create: `backend/tests/test_moderation_priority.py`
- Modify: `backend/tests/test_telemetry_isolation.py`

**Interfaces:**
- Consumes: `QueueSignals`, `ModerationReason`, report counts/reasons, `edited_since_monetized`, and caller-supplied `queued_at`, `now`, and optional manual-escalation flag.
- Produces: `POLICY_VERSION`, `PriorityBand`, `PriorityLane`, `SlaState`, `PriorityFactor`, `PriorityAssessment`, and `evaluate_priority(facts: PriorityFacts, *, now: datetime) -> PriorityAssessment`.

- [ ] **Step 1: Write failing policy tests**

Create table-driven tests that instantiate `PriorityFacts` and pin these results:

```python
def test_collusion_and_duplicate_are_additive_but_score_is_capped():
    facts = PriorityFacts(
        queued_at=NOW - timedelta(hours=1),
        report_count=4,
        report_reasons=frozenset({ModerationReason.fake_proof}),
        edited_since_monetized=True,
        velocity=True,
        collusion=True,
        duplicate_content=True,
        manually_escalated=False,
    )
    result = evaluate_priority(facts, now=NOW)
    assert result.policy_version == "review-priority-v1"
    assert result.integrity_score == 100
    assert result.lane == PriorityLane.reported
    assert [f.code for f in result.factors] == [
        "edited_after_monetization", "collusion", "duplicate_content",
        "vote_velocity", "report_count_4_plus", "report_reason_fake_proof",
    ]


def test_non_inputs_never_appear_in_priority_facts_or_assessment():
    forbidden = {
        "active_ms", "body_active_ms", "scroll_milestone", "first_vote_at",
        "country", "wilson_score", "reputation_score", "trust_stage",
        "verification_status", "star_rating",
    }
    assert forbidden.isdisjoint(PriorityFacts.__dataclass_fields__)
    assert forbidden.isdisjoint(PriorityAssessment.__dataclass_fields__)
```

Also test every individual contribution, highest-only report bracket, highest-only report-reason contribution, 100 cap, lane precedence, 1h/4h/8h/24h SLA boundaries, 75% approaching threshold, band thresholds 15 and 40, overdue promotion, and deterministic order-key ties.

- [ ] **Step 2: Run the policy tests and verify RED**

Run:

```powershell
Set-Location backend
pytest tests/test_moderation_priority.py -q
```

Expected: collection failure because `app.services.moderation_priority` does not exist.

- [ ] **Step 3: Implement the pure policy**

Use frozen dataclasses and string enums. The public shape is:

```python
POLICY_VERSION = "review-priority-v1"

@dataclass(frozen=True)
class PriorityFacts:
    queued_at: datetime
    report_count: int
    report_reasons: frozenset[ModerationReason]
    edited_since_monetized: bool
    velocity: bool
    collusion: bool
    duplicate_content: bool
    manually_escalated: bool = False

@dataclass(frozen=True)
class PriorityFactor:
    code: str
    observed: bool | int | str
    contribution: int
    explanation: str

@dataclass(frozen=True)
class PriorityAssessment:
    policy_version: str
    lane: PriorityLane
    integrity_score: int
    band: PriorityBand
    sla_state: SlaState
    due_at: datetime
    factors: tuple[PriorityFactor, ...]
    order_key: tuple[int, int, int, datetime, datetime]
```

Factor order is the table order in the specification. Lane precedence is escalation, reports, integrity, routine. `quality_audit` exists in the enum but is never returned by this review-submission evaluator. Use timezone-aware UTC datetimes and raise `ValueError` for naive values.

- [ ] **Step 4: Extend isolation assertions**

Add `app.services.moderation_priority` to `DECISION_MODULES` and assert it does not import telemetry models/services or contain any forbidden telemetry field name. Preserve the exact `QueueSignals` field-freeze assertion.

- [ ] **Step 5: Run focused verification and commit**

Run:

```powershell
Set-Location backend
pytest tests/test_moderation_priority.py tests/test_telemetry_isolation.py -q
ruff check app/services/moderation_priority.py tests/test_moderation_priority.py tests/test_telemetry_isolation.py
```

Expected: all pass. Then inspect `git status --short` and `git diff --cached --check`, stage only the three named files, and commit:

```powershell
git commit -m "feat(moderation): define explainable priority policy"
```

---

### Task 2: Canonical queue assessment contract

**Files:**
- Modify: `backend/app/schemas/referral.py`
- Modify: `backend/app/api/v1/routes/admin_referral.py`
- Modify: `backend/app/services/referral_service.py`
- Modify: `backend/app/services/report_service.py`
- Modify: `backend/tests/test_referral_api.py`
- Modify: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: Task 1 `PriorityFacts`, `PriorityAssessment`, and `evaluate_priority`.
- Produces: Pydantic `QueuePriorityFactor`, `QueuePriorityAssessment`, `QueueCounts`, `QueuePage`, and `ReviewQueueResponse`; service `get_prioritized_queue(db, query: QueueQuery, *, now: datetime | None = None) -> QueuePage`.

- [ ] **Step 1: Write failing API contract tests**

Create real-PostgreSQL tests that insert more rows than the page size and assert:

```python
response = client.get(
    "/api/v1/admin/review-queue?limit=2&band=high",
    headers=moderator_headers,
)
assert response.status_code == 200
body = response.json()
assert body["total"] == 3
assert len(body["items"]) == 2
assert all(item["priority"]["band"] == "high" for item in body["items"])
assert body["items"][0]["priority"]["policy_version"] == "review-priority-v1"
assert body["counts"]["by_band"]["high"] == 3
```

Add cases proving a high-priority item outside the old first 50 appears on page one, ties are stable across repeated calls, invalid filters return 422, and non-moderators receive 403.

- [ ] **Step 2: Run focused API tests and verify RED**

Run:

```powershell
Set-Location backend
pytest tests/test_referral_api.py -k "priority or pagination or filter" -q
```

Expected: failures because the response still contains `pending` and `edited_since_monetized` arrays without priority assessments or truthful totals.

- [ ] **Step 3: Add batch report facts**

Add one report-service function:

```python
@dataclass(frozen=True)
class ReportFacts:
    count: int
    reasons: frozenset[ModerationReason]

def report_facts_by_target(
    db: Session,
    target_type: ModerationTargetType,
    target_refs: Collection[uuid.UUID],
) -> dict[uuid.UUID, ReportFacts]:
    ...
```

Implement it as grouped queries over the bounded target set. Count distinct report rows and collect enum reasons without loading notes, evidence URLs, or reporter PII.

- [ ] **Step 4: Add the typed response models**

`QueueItem` gains a sibling `priority: QueuePriorityAssessment`; do not add fields to `QueueSignals`. `ReviewQueueResponse` becomes:

```python
class ReviewQueueResponse(BaseModel):
    items: list[QueueItem]
    total: int
    next_cursor: str | None = None
    counts: QueueCounts
```

`QueuePriorityAssessment` serializes policy version, lane, score, band, SLA state, due time, and factors. `QueueCounts` contains `by_lane`, `by_band`, and `by_sla` maps plus total. Cursor is nullable in this compatibility slice; ordering correctness must not depend on offset.

- [ ] **Step 5: Evaluate, filter, order, then paginate**

Load all eligible pending and edited candidates with products/authors in bounded batched queries. Batch report facts, compute existing fraud signals, call the pure evaluator, apply server filters, sort by assessment order key plus review UUID, compute counts, and only then slice the requested page.

Keep `review.created_at` as the explicit temporary `queued_at` approximation for initial pending reviews and the existing edited timestamp for edited items. Add `queue_time_basis: "review_created_at" | "review_updated_at"` to the response so the UI does not claim precise lifecycle timing before the queue-entry migration.

- [ ] **Step 6: Preserve compatibility while updating callers**

Accept `band`, `lane`, `sla`, `factor`, `q`, `limit`, and `offset` query parameters. Remove the duplicate `pending`/`edited` response only after the Next caller in Task 4 is changed in the same release candidate. No public endpoint changes.

- [ ] **Step 7: Run focused verification and commit**

Run:

```powershell
Set-Location backend
pytest tests/test_moderation_priority.py tests/test_referral_api.py tests/test_reports_api.py tests/test_fraud_signals.py -q
ruff check app/ tests/
```

Expected: all pass or DB-marked tests skip only when the guarded local PostgreSQL fixture is unavailable. Commit only named backend files:

```powershell
git commit -m "feat(moderation): prioritize the full review queue server-side"
```

---

### Task 3: Make Overview consume the canonical policy

**Files:**
- Modify: `backend/app/services/admin_overview_service.py`
- Modify: `backend/app/api/v1/routes/admin_analytics.py`
- Modify: `backend/tests/test_admin_overview.py`

**Interfaces:**
- Consumes: Task 2 queue evaluation/count aggregation.
- Produces: Overview `high_priority`, `urgent`, and queue breakdown values from the same canonical assessments.

- [ ] **Step 1: Replace report-only expectations with shared-policy tests**

Add cases where a collusion-only review, a report-only review, an overdue routine review, and a clear on-track review produce the same High/Normal/Low classification in both queue API and overview.

```python
queue = prioritized_queue(db, now=NOW)
overview = svc.overview(db, now=NOW)
assert overview.high_priority == sum(
    item.priority.band == PriorityBand.high for item in queue.all_items
)
assert overview.urgent == sum(
    item.priority.sla_state == SlaState.overdue for item in queue.all_items
)
```

Update the Flagged breakdown to continue meaning reported targets; it must not be renamed or reused as High.

- [ ] **Step 2: Run the overview tests and verify RED**

Run:

```powershell
Set-Location backend
pytest tests/test_admin_overview.py -q
```

Expected: failures because overview still defines high priority as the reported-review intersection and aliases urgent to that count.

- [ ] **Step 3: Share the assessment aggregation**

Extract a service-level aggregation that both route and overview can call without issuing per-item queries twice. Set:

- `queue_total` to all open review work;
- `high_priority` to canonical High assessments;
- `urgent` to overdue assessments;
- `Flagged` breakdown to distinct reported queue targets.

Add `approaching_sla` and `overdue_sla` fields to the overview response. Keep unavailable-data behavior truthful if assessment loading fails.

- [ ] **Step 4: Run verification and commit**

Run:

```powershell
Set-Location backend
pytest tests/test_admin_overview.py tests/test_referral_api.py tests/test_moderation_priority.py -q
ruff check app/services/admin_overview_service.py app/api/v1/routes/admin_analytics.py tests/test_admin_overview.py
```

Expected: all pass. Commit:

```powershell
git commit -m "fix(admin): unify overview and queue priority totals"
```

---

### Task 4: Render server priority and operational statistics

**Files:**
- Modify: `lib/moderation.ts`
- Modify: `app/moderate/review-queue/page.tsx`
- Modify: `components/admin/review-queue-model.ts`
- Modify: `components/admin/ReviewQueueScreen.tsx`
- Modify: `tests/frontend/review-queue-model.test.mjs`
- Create: `tests/frontend/moderation-priority-contract.test.mjs`

**Interfaces:**
- Consumes: Task 2 `ReviewQueueResponse` JSON and Task 3 overview semantics.
- Produces: URL-driven server filters, canonical priority badge, factor explanations, SLA/queue-time display, and total/count summaries.

- [ ] **Step 1: Write failing frontend contract tests**

Update the queue fixture to include:

```javascript
priority: {
  policy_version: "review-priority-v1",
  lane: "reported",
  integrity_score: 55,
  band: "high",
  sla_state: "approaching",
  due_at: "2026-09-08T16:00:00.000Z",
  factors: [
    { code: "report_count_2_3", observed: 2, contribution: 25,
      explanation: "Two distinct people reported this review." },
    { code: "duplicate_content", observed: true, contribution: 30,
      explanation: "The review body closely matches another review." },
  ],
},
queue_time_basis: "review_created_at",
```

Assert `priorityOf(item)` returns the server band without examining signals, unknown factors render safely, `tabHref` preserves all canonical filters, and local helpers no longer sort or filter by a second priority implementation.

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```powershell
node --import tsx --test tests/frontend/review-queue-model.test.mjs tests/frontend/moderation-priority-contract.test.mjs
```

Expected: failures because `QueueItem` lacks priority and `priorityOf` still derives from signals.

- [ ] **Step 3: Update server data fetching and canonical URL filters**

`getQueue(search)` URL-encodes `band`, `lane`, `sla`, `factor`, `q`, `limit`, and `offset`, and returns `items`, `total`, `counts`, and `fetchedAt`. Do not flatten API failures to a valid empty queue; return a discriminated unavailable state.

`ReviewQueuePage` validates search params, fetches the filtered page server-side, and passes canonical values to the screen. Client controls navigate by URL rather than applying whole-queue claims to one page.

- [ ] **Step 4: Replace the badge heuristic and add explanations**

Render:

- band badge and score;
- lane and SLA state;
- due/queue age with a visible approximation label while `queue_time_basis` uses legacy timestamps;
- factor list beside the badge using server explanations;
- aggregate counts by band/lane/SLA;
- raw signals in the existing Signals panel, explicitly labelled advisory evidence.

Keep Wilson and trust cards labelled context. Preserve Figma spacing, desktop split, current local scrollers, and truthful unavailable states. Do not add decision buttons in this slice.

- [ ] **Step 5: Verify responsive behavior locally**

Run:

```powershell
npm run test:frontend
npm run typecheck
npm run lint
npm run build
```

Use the existing authenticated browser acceptance harness at 1440, 1280, 1024, 768, 393, and 320. Require no document horizontal overflow, no dead filters, consistent selected detail, and no console or request failures.

- [ ] **Step 6: Commit the UI contract**

Inspect `git status --short` and `git diff --cached --check`; stage only the six named frontend/test files and commit:

```powershell
git commit -m "feat(admin): explain moderation priority and SLA"
```

---

### Task 5: Slice verification, independent review, and release gate

**Files:**
- Modify only if a verified defect requires a regression-safe fix.
- Update local-only evidence after release; never commit `.bluntly-autopilot/`.

**Interfaces:**
- Consumes: Tasks 1–4 exact candidate.
- Produces: reviewed candidate eligible for CI, deployment, authenticated acceptance, screenshots, and QA handoff.

- [ ] **Step 1: Run complete safe local gates**

Run backend Ruff and the full no-DB suite; run frontend tests, TypeScript, ESLint, and production build. Confirm migration head remains `0041_reading_telemetry` because this slice adds no migration.

- [ ] **Step 2: Run two-stage independent review**

Dispatch one specification-compliance reviewer and one code-quality/security reviewer. Any Critical or Important finding receives a focused fix, regression test, and re-review.

- [ ] **Step 3: Reconcile the staging boundary and push one candidate**

Verify local-only files are unstaged, run `git diff --cached --check`, confirm intended commits only, push `main`, and record full SHA and CI run ID.

- [ ] **Step 4: Require all four CI jobs**

Require Production guard, Backend no-DB, Frontend, and Backend isolated database green. Record exact isolated PostgreSQL total/runtime, migration/revision result, and milestone total. Do not raise timeouts to conceal a failure.

- [ ] **Step 5: Verify exact-SHA deployment and production behavior**

Measure HEAD, origin/main, CI head, and Vercel source SHA. On exact convergence, use the authenticated Edge session to verify canonical ordering/filtering, explanations, totals, desktop/mobile behavior, and moderator/normal-user RBAC without production role mutations.

- [ ] **Step 6: Capture screenshots and operational evidence**

Capture at minimum 1440px desktop split, 393px queue list, 393px selected detail, and the Overview priority/SLA summary. Store them as release evidence outside tracked source unless the repository already has an approved screenshot-artifact location.

- [ ] **Step 7: Complete public non-exposure, logs, and handoff**

Verify public responses contain no assessment details, staff references, Super Admin flags, secrets, telemetry, or private moderator metadata. Inspect relevant production logs for 5xx/schema/auth errors. Update the connected external QA handoff without claiming independent QA passed.

---

## Follow-on plans

After this slice is accepted, create and execute separate plans in this order:

1. queue lifecycle persistence, claims, and exact SLA timing;
2. structured decision payloads and atomic audit snapshots;
3. Figma decision workflow and responsive action footer;
4. deterministic quality-audit sampling and validated-label research export.

No follow-on plan may introduce a model or use reading telemetry as a decision input.
