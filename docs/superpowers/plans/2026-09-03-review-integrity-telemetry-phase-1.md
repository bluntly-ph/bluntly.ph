# Review Integrity — Behavioral Signal Telemetry Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect conservative per-impression reading and scroll telemetry for every reader — signed-in and signed-out — into a bounded, retention-capped PostgreSQL table that is technically incapable of influencing any score, ranking, moderation decision, or payout.

**Architecture:** One durable row per impression, created immediately by a non-blocking start checkpoint and merged by later cumulative checkpoints through a single `ON CONFLICT DO UPDATE` using `GREATEST`/`COALESCE`, which makes replay and out-of-order delivery no-ops. Identity is two mutually exclusive columns enforced by `CHECK` constraints: a server-derived `users.id` for signed-in readers, or a 24-hour rotating first-party pseudonym for signed-out ones — never both, so no direct account-to-pseudonym linkage key exists. A public Next Route Handler shields the reader with an unconditional 204 while the private backend endpoint performs real validation, authentication, and rate limiting.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL (Supabase transaction pooler); Next.js 16 App Router + React 19 + TypeScript; pytest (`requires_db` marker for DB-backed tests); `node --experimental-strip-types --test` for frontend unit tests.

**Spec:** `docs/superpowers/specs/2026-09-03-review-integrity-telemetry-phase-1-design.md`

## Global Constraints

- **C1.** Phase 1 covers all readers, signed-in and signed-out.
- **C2.** Signed-out readers use a rotating random first-party pseudonymous identifier — never a raw IP, fingerprint, email, user/staff/public ID, URL value, or cross-site identity.
- **C3.** Signed-in identity is server-derived from the authenticated session; no duplicated PII.
- **C4.** Active reading and scroll telemetry are collection-only and technically excluded from authenticity, trust, Wilson ranking, moderator priority, publication, vote weighting, Honesty Fund, payout, and penalties.
- **C5.** Conservative active time = visible AND focused AND recently active AND review/body visible. Sparse local checkpoints. Coarse monotonic scroll milestones. Bounded writes.
- **C6.** Client telemetry is attacker-controlled: validate everything, derive server authority, rate-limit, fail open for core UX.
- **C7.** Coarse geography only, from existing edge data. No GPS, no raw IP.
- **C8.** Additive migrations only. Bounded retention. No arbitrary JSON dump.
- **Pinned values:** `IDLE_MS = 30_000`; `MAX_SESSION_MS = 1_800_000`; `MIN_ACTIVE_MS = 1_000`; `MAX_CHECKPOINTS = 16` (includes the start checkpoint); `SKEW_TOLERANCE_MS = 5_000`; `SCROLL_MILESTONES = (0, 25, 50, 75, 100)`; `RETENTION_DAYS = 90`; `RETENTION_BATCH = 5_000`; `MAX_BATCHES_PER_RUN = 40`; telemetry rate limit `60` per `60s`; reader cookie `bluntly_rid`, `Max-Age=86_400`.
- **Naming:** the vote-geography metric counts **first-time votes only** and is named `review_first_vote_geo_buckets` / `first_vote_count`. Never call it "votes by city".
- **Never persist a raw User-Agent.** Only the derived `device_class` bucket (0 unknown, 1 phone, 2 tablet, 3 desktop).
- **Never add a `GET` route** that returns telemetry.
- **Commit style:** conventional commits with a scope where one applies (`feat(telemetry):`, `test(telemetry):`, `docs:`).

---

## File Structure

**Backend — new**

| File | Responsibility |
|---|---|
| `backend/alembic/versions/0041_reading_telemetry.py` | Enum `reader_kind`, tables `review_reading_sessions` + `review_first_vote_geo_buckets`, indexes, constraints |
| `backend/app/models/telemetry.py` | `ReviewReadingSession` ORM model only |
| `backend/app/services/reading_telemetry_service.py` | Pure clamps, device-class derivation, the UPSERT, `note_vote`, batched purge |
| `backend/app/api/v1/routes/reading_telemetry.py` | Private ingest endpoint: identity resolution, rate limit, real status codes, no `GET` |
| `backend/scripts/export_reading_telemetry.py` | Read-only CSV export for owner-run analysis |
| `backend/tests/test_reading_telemetry.py` | Validation, clamps, UPSERT semantics, constraints, route behaviour |
| `backend/tests/test_telemetry_isolation.py` | Static import isolation, contract freezes, behavioural score/payout equality |

**Backend — modified**

| File | Change |
|---|---|
| `backend/app/models/enums.py` | Add `ReaderKind` |
| `backend/app/models/traffic.py` | Add `ReviewFirstVoteGeoBucket` |
| `backend/app/models/__init__.py` | Register both new models |
| `backend/app/api/v1/router.py` | Include the ingest router |
| `backend/app/core/config.py` | `telemetry_rate_limit_max`, `telemetry_ingest_key`, `telemetry_retention_days` |
| `backend/app/services/request_traffic_service.py` | Add `record_first_vote_geo`, `purge_expired_first_vote_geo` |
| `backend/app/services/vote_service.py` | `cast_vote` returns `CastVoteResult(review, created)` |
| `backend/app/api/v1/routes/reviews.py` | Consume `CastVoteResult`; call `note_vote` and `record_first_vote_geo` |
| `backend/app/services/retention_service.py` | Batched, bounded, observable purges for four tables |
| `backend/scripts/check_invariants.py` | Two telemetry invariants |
| `backend/tests/test_postgrest_surface.py` | Assert the new tables are closed to `anon`/`authenticated` |
| `backend/tests/test_pii_retention.py` | Assert the batched sweeps |

**Frontend — new**

| File | Responsibility |
|---|---|
| `lib/reading-telemetry-events.ts` | `InteractionKind`, `TELEMETRY_EVENT`, `markInteraction` — the only cross-component boundary |
| `lib/reading-telemetry.ts` | Pure, DOM-free accumulator, checkpoint schedule, scroll snapping, payload builder |
| `lib/reader-id.ts` | `server-only`; cookie name, lifetime, shape check, minting |
| `app/api/telemetry/route.ts` | Public POST: pseudonym, bearer, country, user-agent forwarding; always 204 |
| `components/review/ReadingTelemetry.tsx` | `"use client"`; DOM wiring, listeners with cleanup, delegated outlink click |
| `tests/frontend/reading-telemetry.test.mjs` | Accumulator and schedule unit tests |
| `tests/frontend/reading-telemetry-events.test.mjs` | Marker boundary unit tests |

**Frontend — modified**

| File | Change |
|---|---|
| `lib/session.ts` | Clear `bluntly_rid` in `createSession` and `destroySession` |
| `components/review/ReviewVoteBar.tsx` | Emit `vote` marker |
| `components/review/ReportDialog.tsx` | Emit `report` marker |
| `components/review/CommentThread.tsx` | Emit `comment` marker |
| `components/review/ShareButton.tsx` | Emit `share` marker |
| `components/review/ReviewOverflowMenu.tsx` | Emit `share` marker |
| `components/review/ReviewDetail.tsx` | Mount `<ReadingTelemetry>`, add `id="review-body"`, add `data-telemetry-outlink` |
| `components/review/ReviewAside.tsx` | Add `data-telemetry-outlink` |
| `app/privacy/page.tsx` | Plain-language disclosure |

---

## Task 1: Documentation and privacy disclosure

**Files:**
- Create: `docs/superpowers/specs/2026-09-03-review-integrity-telemetry-phase-1-design.md` *(already written this session — commit as-is)*
- Create: `docs/superpowers/plans/2026-09-03-review-integrity-telemetry-phase-1.md` *(this file)*
- Modify: `app/privacy/page.tsx`
- Test: `tests/frontend/privacy-disclosure.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: the disclosure strings other tasks must not contradict.

- [ ] **Step 1: Write the failing test**

Create `tests/frontend/privacy-disclosure.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("../../app/privacy/page.tsx", import.meta.url), "utf8");

test("the policy discloses reading activity in plain words", () => {
  assert.match(SOURCE, /how long a review page is actively open/);
  assert.match(SOURCE, /changes at least every 24 hours/);
  assert.match(SOURCE, /not linked to any account/);
});

test("the policy states the reading-activity retention period", () => {
  assert.match(SOURCE, /Reading-activity records are deleted after 90 days/);
});

test("the disclosure claims no legal basis and no regulatory compliance", () => {
  const added = SOURCE.split("\n").filter((l) => /[Rr]eading activity|Reading-activity/.test(l)).join("\n");
  for (const forbidden of [/lawful basis/i, /legitimate interest/i, /complies with/i, /in compliance with/i, /GDPR/i]) {
    assert.ok(!forbidden.test(added), `disclosure must not assert: ${forbidden}`);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend`
Expected: FAIL — three assertion failures, first `AssertionError: The input did not match the regular expression /how long a review page is actively open/`.

- [ ] **Step 3: Add the disclosure**

In `app/privacy/page.tsx`, append to the `"What we collect"` `ul` `items` array:

```
      "Reading activity — how long a review page is actively open, how far you scroll it, and whether you voted, commented, shared, or reported while reading. For signed-out readers this uses a random identifier stored in a first-party cookie that changes at least every 24 hours and is not linked to any account.",
```

Replace the `"Data retention and security"` paragraph block with:

```tsx
  { type: "h2", text: "Data retention and security" },
  {
    type: "p",
    text: "We keep your information for as long as your account is active or as needed to provide the service, meet legal obligations, and resolve disputes. Reading-activity records are deleted after 90 days. We use reasonable safeguards to protect it, though no online service can promise perfect security.",
  },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend`
Expected: PASS — all three privacy tests pass; the pre-existing `globe-model` tests still pass.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-03-review-integrity-telemetry-phase-1-design.md \
        docs/superpowers/plans/2026-09-03-review-integrity-telemetry-phase-1.md \
        app/privacy/page.tsx tests/frontend/privacy-disclosure.test.mjs
git commit -m "docs(telemetry): approved Phase 1 design, plan, and privacy disclosure"
```

---

## Task 2: Migration and models

**Files:**
- Create: `backend/alembic/versions/0041_reading_telemetry.py`
- Create: `backend/app/models/telemetry.py`
- Modify: `backend/app/models/enums.py`
- Modify: `backend/app/models/traffic.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_reading_telemetry.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `reviews.id`, `users.id`.
- Produces:
  - `app.models.enums.ReaderKind` — `str` enum, members `anon`, `user`.
  - `app.models.telemetry.ReviewReadingSession` — table `review_reading_sessions`, columns exactly as in the migration below.
  - `app.models.traffic.ReviewFirstVoteGeoBucket` — table `review_first_vote_geo_buckets`, columns `id, review_id, bucket_start, country, region, city, first_vote_count, updated_at`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_reading_telemetry.py`:

```python
"""Reading telemetry: constraints, clamps, UPSERT semantics, and the route.

The constraint tests are the load-bearing ones. This subsystem's entire privacy
argument is that a pseudonym and an account can never appear on the same row,
and that is a database CHECK rather than a convention, so it is asserted against
a real PostgreSQL rather than inferred from the shape of the code.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import ReaderKind
from app.models.telemetry import ReviewReadingSession
from tests.conftest import requires_db


def test_reader_kind_has_exactly_two_members():
    assert {m.value for m in ReaderKind} == {"anon", "user"}


def test_the_model_declares_the_columns_the_service_writes():
    cols = set(ReviewReadingSession.__table__.columns.keys())
    assert {
        "impression_id", "review_id", "reader_kind", "reader_ref", "anon_ref",
        "started_at", "last_seen_at", "active_ms", "body_active_ms", "wall_ms",
        "scroll_milestone", "checkpoints", "max_seq", "clamped",
        "vote_client_after_ms", "report_client_after_ms",
        "comment_client_after_ms", "share_client_after_ms",
        "photo_client_after_ms", "outlink_client_after_ms",
        "first_vote_at", "active_ms_at_first_vote", "country",
        "word_count_at_view", "star_rating_at_view", "device_class",
    } <= cols


def test_no_user_agent_column_exists():
    """The raw User-Agent is never persisted — only the derived bucket."""
    cols = set(ReviewReadingSession.__table__.columns.keys())
    assert "user_agent" not in cols
    assert "device_class" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'app.models.telemetry'`.

- [ ] **Step 3: Add the enum**

In `backend/app/models/enums.py`, after `class VoteDirection`:

```python
class ReaderKind(str, enum.Enum):
    """Which identity column on a reading session is populated.

    Exactly one of `reader_ref` / `anon_ref` is non-null, enforced by CHECK
    constraints in migration 0041. This enum names which.
    """

    anon = "anon"
    user = "user"
```

- [ ] **Step 4: Add the model**

Create `backend/app/models/telemetry.py`:

```python
"""review_reading_sessions — one row per review impression, merged in place.

IDENTITY IS TWO COLUMNS, NEVER ONE. `reader_ref` holds a real account;
`anon_ref` holds a rotating 24-hour pseudonym with no preimage. Exactly one is
non-null, enforced by CHECK constraints in migration 0041. This prevents a
direct account-to-pseudonym linkage key; raw access remains restricted because
time, content, and coarse-country correlations can still permit inference.

COLLECTION ONLY. Nothing in this table is read by any code that computes a
score, a rank, a moderator priority, a publication decision, a vote weight, a
fund share, or a payout. `tests/test_telemetry_isolation.py` asserts that.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
    Integer, SmallInteger, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ReaderKind


class ReviewReadingSession(Base):
    __tablename__ = "review_reading_sessions"
    __table_args__ = (
        CheckConstraint("(reader_kind = 'user') = (reader_ref IS NOT NULL)",
                        name="ck_reading_reader_user"),
        CheckConstraint("(reader_kind = 'anon') = (anon_ref IS NOT NULL)",
                        name="ck_reading_reader_anon"),
        CheckConstraint("scroll_milestone IN (0,25,50,75,100)",
                        name="ck_reading_scroll"),
        CheckConstraint("device_class BETWEEN 0 AND 3", name="ck_reading_device"),
        CheckConstraint("active_ms >= 0 AND body_active_ms >= 0 AND wall_ms >= 0",
                        name="ck_reading_ms_signs"),
        CheckConstraint("body_active_ms <= active_ms", name="ck_reading_body_le_act"),
        CheckConstraint(
            "active_ms <= 1800000 AND body_active_ms <= 1800000 "
            "AND wall_ms <= 1800000", name="ck_reading_duration_cap"),
        CheckConstraint("checkpoints BETWEEN 1 AND 16 AND max_seq >= 0",
                        name="ck_reading_checkpoint_cap"),
        CheckConstraint(
            "(vote_client_after_ms IS NULL OR vote_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(report_client_after_ms IS NULL OR report_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(comment_client_after_ms IS NULL OR comment_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(share_client_after_ms IS NULL OR share_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(photo_client_after_ms IS NULL OR photo_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(outlink_client_after_ms IS NULL OR outlink_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(active_ms_at_first_vote IS NULL OR active_ms_at_first_vote BETWEEN 0 AND 1800000)",
            name="ck_reading_interaction_cap"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: Client-generated. Trusted ONLY to group checkpoints and dedupe replays.
    impression_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)

    reader_kind: Mapped[ReaderKind] = mapped_column(
        Enum(ReaderKind, name="reader_kind"), nullable=False)
    reader_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    anon_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    #: SERVER CLOCK ONLY. The client never sends an absolute timestamp, which
    #: removes the whole class of clock-skew and backdating attacks.
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))

    active_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    body_active_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    wall_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    scroll_milestone: Mapped[int] = mapped_column(SmallInteger, nullable=False,
                                                  server_default="0")
    checkpoints: Mapped[int] = mapped_column(SmallInteger, nullable=False,
                                             server_default="0")
    max_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    clamped: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                          server_default="false")

    #: Client-asserted, first-occurrence-wins. Named so nobody mistakes these
    #: for server truth; `first_vote_at` below is the trustworthy half.
    vote_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    report_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    comment_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    share_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    #: Defined, deliberately unwired in Phase 1: the review page renders images
    #: through non-interactive next/image, so there is no photo-open control to
    #: instrument. Present so a future lightbox needs no schema change.
    photo_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    outlink_client_after_ms: Mapped[int | None] = mapped_column(Integer)

    first_vote_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_ms_at_first_vote: Mapped[int | None] = mapped_column(Integer)

    #: Coarse geography: COUNTRY ONLY. City beside a pseudonym would be a
    #: location trail; city stays in the identity-free hourly aggregates.
    country: Mapped[str | None] = mapped_column(String(2))

    #: Confound controls snapshotted at write time, because a review can be
    #: edited and a residual computed against the current text would compare a
    #: reader's behaviour to words they never saw.
    word_count_at_view: Mapped[int | None] = mapped_column(SmallInteger)
    star_rating_at_view: Mapped[int | None] = mapped_column(SmallInteger)
    #: 0 unknown / 1 phone / 2 tablet / 3 desktop. Derived server-side from the
    #: request User-Agent, which is NEVER persisted.
    device_class: Mapped[int] = mapped_column(SmallInteger, nullable=False,
                                              server_default="0")
```

- [ ] **Step 5: Add the first-vote geography model**

Append to `backend/app/models/traffic.py`:

```python
class ReviewFirstVoteGeoBucket(Base):
    """review_first_vote_geo_buckets — FIRST-TIME votes per hour x place.

    The name is the specification. This counts the CREATION of a ReviewVote and
    nothing else: a same-direction retry increments nothing, and a direction
    change increments nothing. Counting those would make the number "vote button
    presses by place", which one user toggling a vote could inflate at will.

    No voter column and no IP, exactly like request_geo_buckets: a row says
    "this review took 12 first-time votes from Cebu in this hour" and cannot say
    by whom. See migration 0041.
    """

    __tablename__ = "review_first_vote_geo_buckets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    first_vote_count: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                                  server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))
```

- [ ] **Step 6: Register both models**

In `backend/app/models/__init__.py`, add the imports and `__all__` entries:

```python
from app.models.telemetry import ReviewReadingSession  # noqa: F401
from app.models.traffic import (  # noqa: F401
    RequestGeoBucket,
    ReviewFirstVoteGeoBucket,
    ReviewViewBucket,
)
```

and append `"ReviewReadingSession", "ReviewFirstVoteGeoBucket"` to `__all__`.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`
Expected: PASS — 3 passed.

- [ ] **Step 8: Write the migration**

Create `backend/alembic/versions/0041_reading_telemetry.py`:

```python
"""reading telemetry: one row per review impression, plus first-vote geography

COLLECTION ONLY. Nothing in either table is read by code that computes a score,
a rank, a moderator priority, a publication decision, a vote weight, a fund
share, or a payout. See docs/superpowers/specs/2026-09-03-review-integrity-
telemetry-phase-1-design.md and tests/test_telemetry_isolation.py.

IDENTITY. Two columns, exactly one non-null, enforced by CHECK rather than by
convention. A signed-in reader's row carries `reader_ref` and no pseudonym; a
signed-out reader's row carries `anon_ref` and no account. They therefore cannot
be joined inside the database, which is the property that makes a rotating
pseudonym meaningfully different from a durable one. `reader_ref` cascades, so
deleting an account erases its reading history with no bespoke code.

WHY NOT ONE POLYMORPHIC COLUMN. It could carry neither the foreign key nor the
cascade, and every future query against it would be ambiguous about what it was
joining.

GEOGRAPHY. `country` only on the impression row. City beside a reader pseudonym
is a coarse location trail; city-level analysis stays in request_geo_buckets,
which carries no identity at all (0032).

Additive: one enum type, two tables, no change to any existing object.

Revision ID: 0041_reading_telemetry
Revises: 0040_role_admin_audit_enum
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0041_reading_telemetry"
down_revision = "0040_role_admin_audit_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    reader_kind = sa.Enum("anon", "user", name="reader_kind")
    reader_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "review_reading_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("impression_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reader_kind", reader_kind, nullable=False),
        sa.Column("reader_ref", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("anon_ref", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("active_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("body_active_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wall_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scroll_milestone", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("checkpoints", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("max_seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clamped", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vote_client_after_ms", sa.Integer, nullable=True),
        sa.Column("report_client_after_ms", sa.Integer, nullable=True),
        sa.Column("comment_client_after_ms", sa.Integer, nullable=True),
        sa.Column("share_client_after_ms", sa.Integer, nullable=True),
        sa.Column("photo_client_after_ms", sa.Integer, nullable=True),
        sa.Column("outlink_client_after_ms", sa.Integer, nullable=True),
        sa.Column("first_vote_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_ms_at_first_vote", sa.Integer, nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("word_count_at_view", sa.SmallInteger, nullable=True),
        sa.Column("star_rating_at_view", sa.SmallInteger, nullable=True),
        sa.Column("device_class", sa.SmallInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("(reader_kind = 'user') = (reader_ref IS NOT NULL)",
                           name="ck_reading_reader_user"),
        sa.CheckConstraint("(reader_kind = 'anon') = (anon_ref IS NOT NULL)",
                           name="ck_reading_reader_anon"),
        sa.CheckConstraint("scroll_milestone IN (0,25,50,75,100)",
                           name="ck_reading_scroll"),
        sa.CheckConstraint("device_class BETWEEN 0 AND 3", name="ck_reading_device"),
        sa.CheckConstraint("active_ms >= 0 AND body_active_ms >= 0 AND wall_ms >= 0",
                           name="ck_reading_ms_signs"),
        sa.CheckConstraint("body_active_ms <= active_ms", name="ck_reading_body_le_act"),
        sa.CheckConstraint(
            "active_ms <= 1800000 AND body_active_ms <= 1800000 "
            "AND wall_ms <= 1800000", name="ck_reading_duration_cap"),
        sa.CheckConstraint("checkpoints BETWEEN 1 AND 16 AND max_seq >= 0",
                           name="ck_reading_checkpoint_cap"),
        sa.CheckConstraint(
            "(vote_client_after_ms IS NULL OR vote_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(report_client_after_ms IS NULL OR report_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(comment_client_after_ms IS NULL OR comment_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(share_client_after_ms IS NULL OR share_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(photo_client_after_ms IS NULL OR photo_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(outlink_client_after_ms IS NULL OR outlink_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(active_ms_at_first_vote IS NULL OR active_ms_at_first_vote BETWEEN 0 AND 1800000)",
            name="ck_reading_interaction_cap"),
    )
    # The UPSERT target AND the replay fence: one impression, one row, forever.
    op.create_index("uq_reading_impression", "review_reading_sessions",
                    ["impression_id"], unique=True)
    # Retention is one indexed range scan over this column.
    op.create_index("ix_reading_started_at", "review_reading_sessions", ["started_at"])
    # The analytical read: "this review's impressions over a window".
    op.create_index("ix_reading_review_started", "review_reading_sessions",
                    ["review_id", "started_at"])
    # Vote-timing join. Partial, so anon rows cost nothing to maintain.
    op.create_index("ix_reading_reader_review", "review_reading_sessions",
                    ["reader_ref", "review_id"],
                    postgresql_where=sa.text("reader_ref IS NOT NULL"))

    op.create_table(
        "review_first_vote_geo_buckets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("first_vote_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    # NULLS NOT DISTINCT matters exactly as it did in 0032: three of these
    # columns are nullable, and under the default two country-only rows for the
    # same hour would never conflict, so every vote would INSERT and the
    # "aggregate" would grow like a log.
    op.execute(
        "CREATE UNIQUE INDEX uq_review_first_vote_geo "
        "ON review_first_vote_geo_buckets "
        "(review_id, bucket_start, country, region, city) NULLS NOT DISTINCT"
    )
    op.create_index("ix_review_first_vote_geo_start",
                    "review_first_vote_geo_buckets", ["bucket_start"])


def downgrade() -> None:
    op.drop_index("ix_review_first_vote_geo_start",
                  table_name="review_first_vote_geo_buckets")
    op.drop_index("uq_review_first_vote_geo",
                  table_name="review_first_vote_geo_buckets")
    op.drop_table("review_first_vote_geo_buckets")
    op.drop_index("ix_reading_reader_review", table_name="review_reading_sessions")
    op.drop_index("ix_reading_review_started", table_name="review_reading_sessions")
    op.drop_index("ix_reading_started_at", table_name="review_reading_sessions")
    op.drop_index("uq_reading_impression", table_name="review_reading_sessions")
    op.drop_table("review_reading_sessions")
    sa.Enum(name="reader_kind").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 9: Verify the migration is additive and correctly ordered**

Run: `cd backend && python -m scripts.check_migration_safety --all`
Expected: exits 0; `0041_reading_telemetry` is reported as a table-creating migration with no destructive operation and no rollout-order requirement.

- [ ] **Step 10: Lint**

Run: `cd backend && python -m ruff check app/ scripts/ tests/`
Expected: `All checks passed!`

- [ ] **Step 11: Commit**

```bash
git add backend/alembic/versions/0041_reading_telemetry.py \
        backend/app/models/telemetry.py backend/app/models/enums.py \
        backend/app/models/traffic.py backend/app/models/__init__.py \
        backend/tests/test_reading_telemetry.py
git commit -m "feat(telemetry): reading-session and first-vote-geo schema"
```

---

## Task 3: Pure clamps, scroll snapping, and device-class derivation

**Files:**
- Create: `backend/app/services/reading_telemetry_service.py`
- Modify: `backend/tests/test_reading_telemetry.py`

**Interfaces:**
- Consumes: `app.models.telemetry.ReviewReadingSession`.
- Produces:
  - `MAX_SESSION_MS = 1_800_000`, `MAX_CHECKPOINTS = 16`, `SKEW_TOLERANCE_MS = 5_000`, `SCROLL_MILESTONES = (0, 25, 50, 75, 100)`, `RETENTION_DAYS = 90`, `RETENTION_BATCH = 5_000`, `MAX_BATCHES_PER_RUN = 40`
  - `@dataclass(frozen=True) Checkpoint` — fields `impression_id: uuid.UUID`, `review_id: uuid.UUID`, `seq: int`, `active_ms: int`, `body_active_ms: int`, `wall_ms: int`, `scroll_pct: int`, `vote_after_ms: int | None`, `report_after_ms: int | None`, `comment_after_ms: int | None`, `share_after_ms: int | None`, `photo_after_ms: int | None`, `outlink_after_ms: int | None`
  - `@dataclass(frozen=True) Clamped` — fields `active_ms: int`, `body_active_ms: int`, `wall_ms: int`, `scroll_milestone: int`, `clamped: bool`
  - `snap_scroll(pct: int) -> int`
  - `device_class_from_user_agent(user_agent: str | None) -> int`
  - `clamp(checkpoint: Checkpoint, *, elapsed_ms: int | None = None) -> Clamped`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_reading_telemetry.py`:

```python
from app.services import reading_telemetry_service as svc


def _cp(**over):
    base = dict(
        impression_id=uuid.uuid4(), review_id=uuid.uuid4(), seq=1,
        active_ms=1000, body_active_ms=800, wall_ms=2000, scroll_pct=50,
        vote_after_ms=None, report_after_ms=None, comment_after_ms=None,
        share_after_ms=None, photo_after_ms=None, outlink_after_ms=None,
    )
    base.update(over)
    return svc.Checkpoint(**base)


# Scroll snapping -----------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (0, 0), (1, 0), (24, 0), (25, 25), (49, 25), (50, 50),
    (74, 50), (75, 75), (99, 75), (100, 100), (-5, 0), (999, 100),
])
def test_scroll_snaps_to_the_five_legal_values(raw, expected):
    assert svc.snap_scroll(raw) == expected


# Device class --------------------------------------------------------------

@pytest.mark.parametrize("ua,expected", [
    (None, 0),
    ("", 0),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1", 1),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari", 1),
    ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1 Mobile", 2),
    ("Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 Safari", 2),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome Safari", 3),
    ("curl/8.4.0", 0),
])
def test_device_class_is_derived_from_the_user_agent(ua, expected):
    assert svc.device_class_from_user_agent(ua) == expected


def test_device_class_is_always_in_range():
    """The CHECK constraint refuses anything else, so the deriver must not
    produce it in the first place."""
    for ua in (None, "", "x" * 5000, "\x00\x01", "Android Mobile iPad"):
        assert 0 <= svc.device_class_from_user_agent(ua) <= 3


# Clamping ------------------------------------------------------------------

def test_active_ms_is_capped_at_the_session_maximum():
    out = svc.clamp(_cp(active_ms=9_000_000, body_active_ms=0, wall_ms=0))
    assert out.active_ms == svc.MAX_SESSION_MS
    assert out.clamped is True


def test_body_active_never_exceeds_active():
    out = svc.clamp(_cp(active_ms=1000, body_active_ms=5000))
    assert out.body_active_ms == 1000
    assert out.clamped is True


def test_wall_ms_is_capped():
    out = svc.clamp(_cp(wall_ms=9_000_000))
    assert out.wall_ms == svc.MAX_SESSION_MS
    assert out.clamped is True


def test_elapsed_time_bounds_the_claimed_active_time():
    """A reader cannot have read for longer than the server has known about
    the impression, plus a skew tolerance."""
    out = svc.clamp(_cp(active_ms=600_000, body_active_ms=0), elapsed_ms=3_000)
    assert out.active_ms == 3_000 + svc.SKEW_TOLERANCE_MS
    assert out.clamped is True


def test_an_honest_checkpoint_is_not_flagged():
    out = svc.clamp(_cp(active_ms=41_210, body_active_ms=38_900,
                        wall_ms=61_004, scroll_pct=75), elapsed_ms=62_000)
    assert (out.active_ms, out.body_active_ms, out.wall_ms) == (41_210, 38_900, 61_004)
    assert out.scroll_milestone == 75
    assert out.clamped is False


def test_clamp_output_satisfies_every_check_constraint():
    """Property: whatever comes in, what comes out is storable."""
    for active, body, wall, scroll in [
        (-5, -5, -5, -5), (10**9, 10**9, 10**9, 10**9),
        (0, 99, 0, 33), (1_800_000, 1_800_000, 1_800_000, 100),
    ]:
        out = svc.clamp(_cp(active_ms=active, body_active_ms=body,
                            wall_ms=wall, scroll_pct=scroll))
        assert 0 <= out.active_ms <= svc.MAX_SESSION_MS
        assert 0 <= out.body_active_ms <= out.active_ms
        assert 0 <= out.wall_ms <= svc.MAX_SESSION_MS
        assert out.scroll_milestone in svc.SCROLL_MILESTONES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`
Expected: FAIL — collection error, `ImportError: cannot import name 'reading_telemetry_service' from 'app.services'`.

- [ ] **Step 3: Write the service module**

Create `backend/app/services/reading_telemetry_service.py`:

```python
"""Reading telemetry: clamp it, merge it, and forget it on time.

COLLECTION ONLY. Nothing here is called by code that computes a score, a rank,
a moderator priority, a publication decision, a vote weight, a fund share, or a
payout. `tests/test_telemetry_isolation.py` asserts that by import analysis, so
the guarantee survives a refactor that forgets this comment.

THE CLIENT IS AN ATTACKER. Every millisecond in a payload is a claim, not a
measurement. What makes the dataset usable anyway is that the values a claim
cannot reach — identity, both timestamps, device class, country, the review's
own word count and rating — are all derived here, and that the values a claim
CAN reach are bounded three times over: clamped against wall-clock the server
itself observed, merged monotonically so a claim can never lower a stored
number, and finally refused by CHECK constraints if the clamping is ever wrong.

`clamped` is stored rather than swallowed: a poisoned or buggy row stays visible
in the dataset instead of being silently normalised into a plausible one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.enums import ReaderKind
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession

log = get_logger("reading_telemetry")

#: Hard ceiling on a single impression. Thirty minutes of ACTIVE reading on one
#: review is already implausible; beyond it the number is noise either way.
MAX_SESSION_MS = 1_800_000

#: Writes per impression, enforced in SQL so a client that ignores its own cap
#: still cannot pump one row. Includes the start checkpoint.
MAX_CHECKPOINTS = 16

#: Allowance for clock and network skew when bounding claimed active time
#: against server-observed elapsed time.
SKEW_TOLERANCE_MS = 5_000

#: The only scroll values that may be stored. A continuous percentage would be
#: a higher-resolution behavioural fingerprint for no analytical gain.
SCROLL_MILESTONES = (0, 25, 50, 75, 100)

#: Matches request_geo_buckets, review_view_buckets and the dashboard's own
#: 90-day cap, so no surface can offer a window it has no data for.
RETENTION_DAYS = 90
#: Rows per DELETE statement, and statements per scheduled execution. Together
#: they bound one run at 200,000 rows per table — see purge_expired.
RETENTION_BATCH = 5_000
MAX_BATCHES_PER_RUN = 40


@dataclass(frozen=True)
class Checkpoint:
    """One client-asserted checkpoint. Every field is a claim."""

    impression_id: uuid.UUID
    review_id: uuid.UUID
    seq: int
    active_ms: int
    body_active_ms: int
    wall_ms: int
    scroll_pct: int
    vote_after_ms: int | None
    report_after_ms: int | None
    comment_after_ms: int | None
    share_after_ms: int | None
    photo_after_ms: int | None
    outlink_after_ms: int | None


@dataclass(frozen=True)
class Clamped:
    """A checkpoint reduced to values the database will actually accept."""

    active_ms: int
    body_active_ms: int
    wall_ms: int
    scroll_milestone: int
    clamped: bool


def snap_scroll(pct: int) -> int:
    """The deepest legal milestone at or below `pct`.

    Snapping DOWN rather than to the nearest keeps the number conservative: a
    reader who reached 74% is credited with 50, never with 75.
    """
    value = max(0, min(int(pct), 100))
    return max(m for m in SCROLL_MILESTONES if m <= value)


def device_class_from_user_agent(user_agent: str | None) -> int:
    """0 unknown / 1 phone / 2 tablet / 3 desktop.

    Derived here and never accepted from the payload: a client-supplied device
    field would be one more attacker-controlled column for no gain. The raw
    string is NEVER persisted — only this bucket — because storing it would add
    exactly the fingerprinting surface this subsystem exists to avoid.

    Tablets are tested before phones on purpose. An iPad's user agent contains
    "Mobile", and an Android tablet is identified by "Android" WITHOUT
    "Mobile", so the phone test would claim both.
    """
    ua = (user_agent or "").lower()
    if not ua:
        return 0
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return 2
    if any(token in ua for token in ("iphone", "ipod", "mobi", "android")):
        return 1
    # A browser we could not classify but which is clearly a browser. Anything
    # else — curl, a scraper, a blank header — stays "unknown" rather than
    # being counted as a desktop reader.
    if any(token in ua for token in ("mozilla", "webkit", "gecko", "trident")):
        return 3
    return 0


def clamp(checkpoint: Checkpoint, *, elapsed_ms: int | None = None) -> Clamped:
    """Reduce a claim to something storable, and say whether it had to change.

    `elapsed_ms` is milliseconds since the server created this impression's row.
    It is None on the very first checkpoint, where there is nothing yet to
    compare against.
    """
    dirty = False

    active = max(0, int(checkpoint.active_ms))
    if active != checkpoint.active_ms:
        dirty = True
    if active > MAX_SESSION_MS:
        active, dirty = MAX_SESSION_MS, True
    if elapsed_ms is not None:
        ceiling = max(0, int(elapsed_ms)) + SKEW_TOLERANCE_MS
        if active > ceiling:
            active, dirty = ceiling, True

    body = max(0, int(checkpoint.body_active_ms))
    if body != checkpoint.body_active_ms:
        dirty = True
    if body > active:
        body, dirty = active, True

    wall = max(0, int(checkpoint.wall_ms))
    if wall != checkpoint.wall_ms:
        dirty = True
    if wall > MAX_SESSION_MS:
        wall, dirty = MAX_SESSION_MS, True

    milestone = snap_scroll(checkpoint.scroll_pct)
    if milestone != checkpoint.scroll_pct:
        dirty = True

    return Clamped(active_ms=active, body_active_ms=body, wall_ms=wall,
                   scroll_milestone=milestone, clamped=dirty)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`
Expected: PASS — 26 passed (3 from Task 2, 23 added here).

- [ ] **Step 5: Lint and commit**

```bash
cd backend && python -m ruff check app/ scripts/ tests/
cd ..
git add backend/app/services/reading_telemetry_service.py backend/tests/test_reading_telemetry.py
git commit -m "feat(telemetry): server-side clamps, scroll snapping, device-class derivation"
```

---

## Task 4: Monotonic checkpoint storage and private ingestion

**Files:**
- Modify: `backend/app/services/reading_telemetry_service.py`
- Create: `backend/app/api/v1/routes/reading_telemetry.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `backend/.env.test.example`
- Test: `backend/tests/test_reading_telemetry.py`

**Interfaces:**
- Consumes: `ReviewReadingSession`, `ReaderKind`, `auth_rate_limiter`, and the
  clamp/device helpers from Task 3.
- Produces:
  - `Checkpoint(BaseModel)` with `extra="forbid"` and only the twelve client
    fields from spec §7.2.
  - `ReaderIdentity(kind: ReaderKind, reader_ref: UUID | None,
    anon_ref: UUID | None)`.
  - `record_checkpoint(db, checkpoint, identity, *, country, user_agent) -> bool`.
  - private `POST /api/v1/internal/reading-telemetry`; no GET handler.

- [ ] **Step 1: Add failing pure validation and PostgreSQL behavior tests**

Append tests named exactly, each using literal inputs and persisted-row
assertions:

- `test_checkpoint_forbids_unknown_identity_fields`: construct with `user_id`,
  `country`, `occurred_at`, and `device_class` one at a time; each raises a
  Pydantic validation error.
- `test_checkpoint_rejects_negative_or_non_finite_durations`: negative values,
  JSON non-numbers, and integers above `2_147_483_647` are rejected.
- `test_checkpoint_accepts_only_uuid4_impressions`: UUIDv1 is rejected and a
  literal UUIDv4 is accepted.
- `test_first_checkpoint_creates_one_server_derived_user_row`: persisted row has
  `reader_ref=user.id`, `anon_ref=None`, `checkpoints=1`, `max_seq=0`.
- `test_first_checkpoint_creates_one_anon_row_without_user_identity`: the inverse
  identity fields are persisted.
- `test_replay_and_older_sequence_are_noops`: identical and lower sequence
  payloads leave every stored field unchanged.
- `test_later_checkpoint_advances_only_monotonic_fields`: higher cumulative
  values advance and lower values cannot regress.
- `test_cross_reader_and_cross_review_replays_change_nothing`: reuse one
  impression UUID with a different identity/review and compare the full row.
- `test_the_seventeenth_checkpoint_is_refused`: sequences 0–15 land; sequence 16
  changes no field and the count remains 16.
- `test_interaction_markers_are_first_occurrence_wins`: the first non-null value
  remains after a later different claim.
- `test_server_clamps_active_time_to_elapsed_time`: a 30-minute claim immediately
  after start stores no more than the 5-second skew allowance and sets `clamped`.

Use hand-authored UUIDs and literals. For every no-op assertion, snapshot the
real row with `tuple(row.__table__.columns)` before the request and compare the
same fields afterward; do not assert against a mock call.

- [ ] **Step 2: Run and verify RED**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`

Expected: pure validation tests fail because `Checkpoint` is missing; DB tests
skip locally when the isolated PostgreSQL configuration is absent.

- [ ] **Step 3: Implement the typed contract and one-statement UPSERT**

Add these public types and signature to the service:

```python
class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impression_id: uuid.UUID
    review_id: uuid.UUID
    seq: int = Field(ge=0, le=2_147_483_647)
    active_ms: int = Field(ge=0, le=2_147_483_647)
    body_active_ms: int = Field(ge=0, le=2_147_483_647)
    wall_ms: int = Field(ge=0, le=2_147_483_647)
    scroll_pct: Literal[0, 25, 50, 75, 100]
    vote_after_ms: int | None = Field(default=None, ge=0)
    report_after_ms: int | None = Field(default=None, ge=0)
    comment_after_ms: int | None = Field(default=None, ge=0)
    share_after_ms: int | None = Field(default=None, ge=0)
    photo_after_ms: int | None = Field(default=None, ge=0)
    outlink_after_ms: int | None = Field(default=None, ge=0)

@dataclass(frozen=True)
class ReaderIdentity:
    kind: ReaderKind
    reader_ref: uuid.UUID | None = None
    anon_ref: uuid.UUID | None = None

def record_checkpoint(
    db: Session,
    checkpoint: Checkpoint,
    identity: ReaderIdentity,
    *,
    country: str | None,
    user_agent: str | None,
) -> bool:
    """Validate, clamp, and monotonically merge one checkpoint.

    Return true only when the INSERT/UPSERT changes one row. The implementation
    is the single PostgreSQL statement and validation sequence below.
    """
```

Validate `impression_id.version == 4`, validate the review exists, derive
`word_count_at_view` and `star_rating_at_view` from that review, and derive only
the coarse device bucket from `user_agent`. Never persist the raw header. Use
`sqlalchemy.dialects.postgresql.insert` with the exact identity/review/sequence/
checkpoint predicates from spec §7.4. Set `checkpoints=1` on insert, so the
immediate start counts toward the cap. Commit only when the statement changes a
row and return `rowcount == 1`.

- [ ] **Step 4: Add failing private-route tests**

Add six route tests: missing/wrong server key returns 401 and writes zero rows;
valid bearer plus anonymous header stores only the user; valid anonymous header
without bearer stores only the pseudonym; body identity fields produce 422;
malformed payload produces 422; and FastAPI's registered route methods contain
POST but not GET for the private path.

The route tests must inspect persisted rows for identity behavior. The no-GET
test inspects FastAPI's registered methods, rather than grepping source text.

- [ ] **Step 5: Run and verify RED**

Run: `cd backend && python -m pytest tests/test_reading_telemetry.py -q`

Expected: route tests fail with 404 because the router is not registered.

- [ ] **Step 6: Implement the private route and configuration**

Require `X-Telemetry-Key` for every write and compare with
`secrets.compare_digest`. Resolve a valid bearer through the existing security
layer; otherwise require a valid `X-Reader-Anon` UUID. A valid signed-in user
always wins and the anonymous header is discarded. Normalize `X-Reader-Country`
to an ISO alpha-2 value or `None`. Apply the existing limiter under the
`reading_telemetry` bucket at 60 requests/60 seconds. Return real 401/422/429
responses from this private route and 204 only after an accepted/no-op write.

Add non-secret names/defaults to both environment templates:

```ini
TELEMETRY_INGEST_KEY=
TELEMETRY_RATE_LIMIT_MAX=60
TELEMETRY_RETENTION_DAYS=90
```

- [ ] **Step 7: Verify, lint, and commit**

```bash
cd backend
python -m pytest tests/test_reading_telemetry.py -q
python -m ruff check app/ scripts/ tests/
cd ..
git add backend/app/services/reading_telemetry_service.py \
        backend/app/api/v1/routes/reading_telemetry.py \
        backend/app/api/v1/router.py backend/app/core/config.py \
        backend/tests/test_reading_telemetry.py .env.example \
        backend/.env.test.example
git commit -m "feat(telemetry): validate and merge private reading checkpoints"
```

---

## Task 5: Rotating anonymous identity and fail-open Next route

**Files:**
- Create: `lib/reader-id.ts`
- Create: `app/api/telemetry/route.ts`
- Modify: `lib/session.ts`
- Test: `tests/frontend/reader-id.test.mjs`
- Test: `tests/frontend/telemetry-route.test.mjs`

**Interfaces:**
- Produces `READER_COOKIE_NAME`, `READER_COOKIE_MAX_AGE`,
  `validReaderId(value)`, `mintReaderId()`, and `clearReaderId(cookieStore)`.
- The browser-facing route accepts only POST and always returns an empty 204.

- [ ] **Step 1: Write failing identity-helper tests**

```js
test("minted reader identifiers are random UUIDv4 values", () => {
  const values = new Set(Array.from({ length: 64 }, () => mintReaderId()));
  assert.equal(values.size, 64);
  for (const value of values) assert.match(value, UUID_V4);
});

test("reader identity policy is 24 hours and first party", () => {
  assert.equal(READER_COOKIE_NAME, "bluntly_rid");
  assert.equal(READER_COOKIE_MAX_AGE, 86_400);
});

test("hardware and network inputs are not accepted by the minting API", () => {
  assert.equal(mintReaderId.length, 0);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm run test:frontend`

Expected: module-not-found failure for `lib/reader-id.ts`.

- [ ] **Step 3: Implement the server-only identity helper**

Use `crypto.randomUUID()` with no inputs. The route sets `httpOnly`, production
`secure`, `sameSite: "lax"`, `path: "/"`, and `maxAge: 86_400`. Export no
function that accepts IP, user-agent, screen, canvas, font, or hardware values.

- [ ] **Step 4: Write failing public-route behavior tests**

Test the exported request handler with real `Request` objects and a local fake
upstream fetch at the fetch boundary. Cover six literal cases: payload forwarding
without client identity/location/timestamp; server-derived country/user-agent;
204 shielding for upstream 422/429/500; 204 shielding for a thrown fetch;
non-forwarding of oversized/invalid bodies; and the exact private 24-hour
`Set-Cookie` attributes for a new pseudonym.

The captured upstream request must have no `cookie` header, no client-supplied
`authorization`, and no body keys outside spec §7.2. The server may add only
`Authorization`, `X-Reader-Anon`, `X-Reader-Country`, `User-Agent`,
`X-Telemetry-Key`, and content headers.

- [ ] **Step 5: Implement the route and login/logout rotation**

Read at most 4096 body bytes and parse JSON. On any parse/shape/upstream error,
return `new Response(null, { status: 204 })`. Read the session cookie only
server-side and attach it as Bearer. Mint/use the reader cookie server-side;
client JavaScript never reads it. Forward to the configured API origin with the
server-only key and `cache: "no-store"`.

In both `createSession` and `destroySession`, delete `bluntly_rid` before
setting/deleting `bluntly_session`. This makes every login/logout an identity
boundary even when the prior cookie still has time remaining.

- [ ] **Step 6: Verify and commit**

```bash
npm run test:frontend
npx tsc --noEmit
git add lib/reader-id.ts app/api/telemetry/route.ts lib/session.ts \
        tests/frontend/reader-id.test.mjs tests/frontend/telemetry-route.test.mjs
git commit -m "feat(telemetry): rotate anonymous reader identity at session boundaries"
```

---

## Task 6: Pure browser accumulator and interaction event boundary

**Files:**
- Create: `lib/reading-telemetry.ts`
- Create: `lib/reading-telemetry-events.ts`
- Create: `tests/frontend/reading-telemetry.test.mjs`
- Create: `tests/frontend/reading-telemetry-events.test.mjs`

**Interfaces:**
- `ReadingAccumulator.advance(nowMs, gates)` advances cumulative wall/active/body
  counters from a monotonic clock.
- `ReadingAccumulator.noteActivity(nowMs)` resets the 30-second idle window.
- `ReadingAccumulator.noteInteraction(kind, nowMs)` records first occurrence.
- `snapScroll(percent)` returns only `0|25|50|75|100` and never decreases through
  `ReadingAccumulator.noteScroll(percent)`.
- `nextCheckpoint(activeMs, sentThresholds)` yields only
  `10_000,30_000,60_000,120_000,+120_000` thresholds.
- `payload(impressionId, reviewId, seq)` returns exactly the client contract.
- `markInteraction(reviewId, kind)` dispatches the namespaced CustomEvent and is
  a no-op under SSR.

- [ ] **Step 1: Write the accumulator tests and verify RED**

Use literal time deltas to cover eight behaviors: all three page gates are
required; idle gaps are not backfilled and activity resumes; body timing has its
fourth gate; scroll values are coarse/monotonic; the schedule stops at sixteen;
start is sequence zero and later values are cumulative; the payload key set has
no identity/location/device/absolute-time/URL; and every interaction kind is
first-occurrence-wins.

Run: `npm run test:frontend`

Expected: module-not-found failures for both new modules.

- [ ] **Step 2: Implement the pure state machine**

Use `performance.now()` values supplied by the caller; never call `Date.now()`.
The `gates` value is exactly:

```ts
export type ActivityGates = {
  visible: boolean;
  focused: boolean;
  recentlyActive: boolean;
  bodyVisible: boolean;
};
```

`activeMs` advances only when the first three gates are true;
`bodyActiveMs` advances only when all four are true. `wallMs` advances by the
non-negative monotonic delta regardless of gates and all counters stop at
1,800,000. The payload key set exactly matches spec §7.2.

- [ ] **Step 3: Implement and test the typed marker boundary**

```ts
export const TELEMETRY_EVENT = "bluntly:review-interaction";
export type InteractionKind =
  | "vote" | "report" | "comment" | "share" | "photo" | "outlink";
export type InteractionDetail = { reviewId: string; kind: InteractionKind };

export function markInteraction(reviewId: string, kind: InteractionKind): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<InteractionDetail>(TELEMETRY_EVENT, {
    detail: { reviewId, kind },
  }));
}
```

Test that the real event reaches a real `EventTarget`, carries only the two
declared fields, and one review ID cannot be mistaken for another.

- [ ] **Step 4: Verify and commit**

```bash
npm run test:frontend
npx tsc --noEmit
git add lib/reading-telemetry.ts lib/reading-telemetry-events.ts \
        tests/frontend/reading-telemetry.test.mjs \
        tests/frontend/reading-telemetry-events.test.mjs
git commit -m "feat(telemetry): conservative reading accumulator and markers"
```

---

## Task 7: Review-page lifecycle instrumentation

**Files:**
- Create: `components/review/ReadingTelemetry.tsx`
- Modify: `components/review/ReviewDetail.tsx`
- Modify: `components/review/ReviewAside.tsx`
- Modify: `components/review/ReviewVoteBar.tsx`
- Modify: `components/review/ReportDialog.tsx`
- Modify: `components/review/CommentThread.tsx`
- Modify: `components/review/ShareButton.tsx`
- Modify: `components/review/ReviewOverflowMenu.tsx`
- Test: `tests/frontend/reading-telemetry.test.mjs`
- Test: `e2e/reading-telemetry.spec.ts`

**Interfaces:**
- Consumes only the pure state machine and `markInteraction` boundary from
  Task 6.
- Produces a component that renders `null` and has no user-visible failure state.

- [ ] **Step 1: Write failing lifecycle and fail-open acceptance tests**

Add six Playwright cases that mount a real review page and intercept only
`/api/telemetry`: forced failures preserve rendering/voting; the first body is
sequence zero and later requests are sparse/cumulative; hidden/unfocused/idle
intervals do not advance active time; scroll bodies contain only monotonic legal
milestones; pagehide flushes only changed state under the cap; and navigation
away/back produces one observer/listener set rather than duplicate requests.

Use fake browser time for deterministic interval assertions. Assert request
bodies, not implementation call counts, and assert the review heading/vote
controls still work under forced telemetry 500s.

- [ ] **Step 2: Run and verify RED**

Run: `npx playwright test e2e/reading-telemetry.spec.ts`

Expected: failure because no telemetry request is emitted.

- [ ] **Step 3: Implement the lifecycle component**

On mount, create one UUIDv4 `impressionId`, instantiate the accumulator, and
fire an unawaited sequence-0 start payload. Update local counters on a 1-second
timer; network writes occur only at the approved active-time thresholds, at a
changed terminal state, and at interaction completion. Use:

- `visibilitychange`, `focus`, `blur`, and `pagehide`;
- activity signals `pointermove`, `pointerdown`, `keydown`, `wheel`, `scroll`,
  and `touchstart`, with passive listeners where applicable;
- one `IntersectionObserver` for `#review-body`;
- one `TELEMETRY_EVENT` listener filtered by `reviewId`;
- one delegated document click listener for `a[data-telemetry-outlink]`.

Every listener, interval, and observer is removed/disconnected in the effect
cleanup. Use `navigator.sendBeacon` for terminal flush and fall back to
`fetch(..., { keepalive: true })` when it returns false. Never enter React state
for telemetry success/failure.

- [ ] **Step 4: Wire the body, outbound links, and successful interactions**

Mount `<ReadingTelemetry reviewId={data.id} />` once per review detail and put
`id="review-body"` on the discussion body container. Add
`data-telemetry-outlink` only to product/referral purchase anchors.

Call `markInteraction(reviewId, kind)` only after the existing action succeeds:
successful non-remove vote, accepted report, created comment, successful Web
Share/clipboard copy. Do not emit for cancelled dialogs, failed requests, or
vote removal. Keep `photo` unwired because no interactive photo viewer exists.

- [ ] **Step 5: Verify and commit**

```bash
npm run test:frontend
npx tsc --noEmit
npm run lint
npx playwright test e2e/reading-telemetry.spec.ts
git add components/review/ReadingTelemetry.tsx components/review/ReviewDetail.tsx \
        components/review/ReviewAside.tsx components/review/ReviewVoteBar.tsx \
        components/review/ReportDialog.tsx components/review/CommentThread.tsx \
        components/review/ShareButton.tsx \
        components/review/ReviewOverflowMenu.tsx \
        tests/frontend/reading-telemetry.test.mjs e2e/reading-telemetry.spec.ts
git commit -m "feat(telemetry): instrument active review reading and interactions"
```

---

## Task 8: Server-authoritative vote timing and first-vote geography

**Files:**
- Modify: `backend/app/services/vote_service.py`
- Modify: `backend/app/services/reading_telemetry_service.py`
- Modify: `backend/app/services/request_traffic_service.py`
- Modify: `backend/app/api/v1/routes/reviews.py`
- Test: `backend/tests/test_votes_api.py`
- Test: `backend/tests/test_reading_telemetry.py`
- Test: `backend/tests/test_request_distribution.py`

**Interfaces:**
- `CastVoteResult(review: Review, created: bool)` replaces the route-consumed
  return value of `cast_vote`.
- `note_vote(db, review_id, reader_id) -> bool` never raises and stamps only the
  most recent still-open signed-in impression.
- `record_first_vote_geo(db, review_id, geo) -> bool` increments only on
  `CastVoteResult.created` and stores no voter identifier.

- [ ] **Step 1: Write failing vote-result and telemetry-isolation tests**

Add six PostgreSQL-backed cases: `created` is true only on first insert;
same-direction retry and direction change are false; a successful vote stamps
the latest matching impression; a forced telemetry exception still leaves the
real vote/Wilson result committed; only the first vote increments the aggregate;
and reflected table columns contain neither voter identity nor IP.

For the fail-open test, force only the telemetry function to raise after the
real vote service commits; then assert the persisted vote and Wilson counters,
not the mock invocation.

- [ ] **Step 2: Run and verify RED**

Run: `cd backend && python -m pytest tests/test_votes_api.py tests/test_reading_telemetry.py tests/test_request_distribution.py -q`

Expected: failures because `CastVoteResult`, `note_vote`, and the new aggregate
writer do not exist.

- [ ] **Step 3: Implement the server-authoritative tail**

Create a frozen dataclass:

```python
@dataclass(frozen=True)
class CastVoteResult:
    review: Review
    created: bool
```

Return `created=True` only when `ReviewVote` was absent before the successful
flush. In the route, obtain the result, then run `note_vote`; if `created`, run
the geography UPSERT. Each telemetry helper owns a separate best-effort
transaction boundary, rolls back on failure, logs only review/action/count
metadata, and never changes the already committed vote response.

`note_vote` updates the latest signed-in row for `(reader_ref, review_id)` whose
`started_at` is within 30 minutes, with `COALESCE(first_vote_at, now())` and the
row's current `active_ms`. `record_first_vote_geo` copies the existing
`RequestGeo` normalizer and `NULLS NOT DISTINCT` UPSERT pattern, incrementing
`first_vote_count` by one.

- [ ] **Step 4: Verify and commit**

```bash
cd backend
python -m pytest tests/test_votes_api.py tests/test_reading_telemetry.py \
  tests/test_request_distribution.py -q
python -m ruff check app/ scripts/ tests/
cd ..
git add backend/app/services/vote_service.py \
        backend/app/services/reading_telemetry_service.py \
        backend/app/services/request_traffic_service.py \
        backend/app/api/v1/routes/reviews.py backend/tests/test_votes_api.py \
        backend/tests/test_reading_telemetry.py \
        backend/tests/test_request_distribution.py
git commit -m "feat(telemetry): record server-authoritative first-vote context"
```

---

## Task 9: Bounded retention, research export, and aggregate health

**Files:**
- Modify: `backend/app/services/retention_service.py`
- Create: `backend/scripts/export_reading_telemetry.py`
- Modify: `backend/scripts/check_invariants.py`
- Test: `backend/tests/test_pii_retention.py`
- Test: `backend/tests/test_reading_telemetry.py`

**Interfaces:**
- `bounded_purge(db, table, time_column, cutoff, *, batch_size=5000,
  max_batches=40) -> PurgeResult(deleted, ceiling_hit)`.
- `run_retention_sweep` returns the existing keys plus `reading_sessions`,
  `review_view_buckets`, `request_geo_buckets`, and `first_vote_geo_buckets`.
- The exporter writes only to an explicitly named local CSV and offers modes
  `readings`, `vote-timing`, `relationships`, and `geo-summary`; it never mutates
  the database and never exposes an HTTP route.

- [ ] **Step 1: Write failing bounded-retention tests**

Add six PostgreSQL-backed cases: expired reading rows are deleted in the
configured batch size; in-window rows survive; review-view retention runs
without ingestion; request-geography retention runs without ingestion;
first-vote-geography retention is idempotent; and a one-batch ceiling reports
remaining work while the next invocation continues it.

Insert `batch_size + 1` deterministic rows and invoke the helper with
`max_batches=1` so the ceiling behavior is proven without creating a huge test.

- [ ] **Step 2: Run and verify RED**

Run: `cd backend && python -m pytest tests/test_pii_retention.py -q`

Expected: failures because the new tables are not purged and the historical
review-view gap remains.

- [ ] **Step 3: Implement batched scheduled retention**

Use PostgreSQL-compatible bounded deletes:

```sql
DELETE FROM <allow-listed table>
WHERE id IN (
  SELECT id FROM <allow-listed table>
  WHERE <allow-listed time column> < :cutoff
  ORDER BY id
  LIMIT :batch
)
```

Table and column names come only from an internal constant allow-list; values
remain bound parameters. Loop at most 40 batches per table, commit each batch,
return totals, and log a warning containing only the table name and count when
the ceiling is reached. The existing scheduled `pii_retention` task consumes
the expanded count dictionary unchanged.

- [ ] **Step 4: Write failing export and invariant tests**

Add four real-database cases: export changes no database row and creates only
the explicit destination; relationship export ignores an author's 31st older
review; geography export uses aggregate columns without voter identity; and the
strict invariant functions identify dual/no identity plus expired rows.

The export fixtures use literal expected CSV headers and values. Assert the
database transaction has no INSERT/UPDATE/DELETE side effects.

- [ ] **Step 5: Implement the owner-run exporter and invariants**

Require `--output <path>` and `--mode`; refuse stdout for raw readings. Limit
every query by `--since-days` in `1..90`. The relationship mode derives voter
presence from existing `review_votes` over at most 30 recent published reviews
and does not persist an edge table. The geo mode exports only aggregate bucket
rows. Add strict invariant checks for dual/no identity and rows older than the
retention cutoff. Operational output is counts only—never payloads, pseudonyms,
user IDs, email, staff refs, or location tied to a reader.

- [ ] **Step 6: Verify and commit**

```bash
cd backend
python -m pytest tests/test_pii_retention.py tests/test_reading_telemetry.py -q
python -m ruff check app/ scripts/ tests/
cd ..
git add backend/app/services/retention_service.py \
        backend/scripts/export_reading_telemetry.py \
        backend/scripts/check_invariants.py backend/tests/test_pii_retention.py \
        backend/tests/test_reading_telemetry.py
git commit -m "feat(telemetry): bound retention and add read-only research export"
```

---

## Task 10: Decision-isolation and public non-exposure proofs

**Files:**
- Create: `backend/tests/test_telemetry_isolation.py`
- Modify: `backend/tests/test_postgrest_surface.py`
- Modify: `backend/tests/test_openapi_contract.py`
- Modify: `backend/tests/test_schema_agreement.py` only if its explicit model list
  requires registration beyond `models/__init__.py`

**Interfaces:**
- Produces no runtime API. These tests are the permanent boundary preventing a
  later feature from silently coupling research data to decisions or money.

- [ ] **Step 1: Write the failing static dependency test**

Parse Python imports with `ast` for the production decision modules listed in
spec §8. Fail if any imports `app.models.telemetry` or
`app.services.reading_telemetry_service`, except that the vote route is allowed
to call the write-only `note_vote` tail. Do not grep prose or exact source lines.

Also assert the real `DashboardSummary` behavior still returns
`average_read_seconds is None` and names it in `unavailable`, and the real
moderator queue schema has no telemetry fields.

- [ ] **Step 2: Write PostgreSQL-backed equality tests and verify RED**

Build deterministic real rows, snapshot these literal outputs, insert extreme
telemetry, recompute, and assert byte/value identity:

Add four real-database equality cases for Wilson/trust/reputation/fraud,
moderator priority/publication, Honesty Fund recipient amounts, and internal
payout eligibility/amounts. Each compares literal serialized outputs across
absent, extreme-present, and deleted-again telemetry states.

Each test runs the real service once without telemetry, once with capped 30
minute/100%-scroll rows for authenticated and anonymous readers, and once after
deleting those rows. All three outputs must match. Keep payouts internal; never
call PayPal or an external provider.

Run: `cd backend && python -m pytest tests/test_telemetry_isolation.py -q`

Expected locally: static tests fail until imports/contracts are correct; DB
equality tests skip without isolated PostgreSQL.

- [ ] **Step 3: Prove storage and API non-exposure**

Extend the real PostgREST privilege test so both new tables are unreadable and
unwritable by `anon` and `authenticated`. Extend OpenAPI traversal to assert no
response schema or GET operation contains:

```python
FORBIDDEN = {
    "anon_ref", "reader_ref", "impression_id", "reader_kind",
    "active_ms", "body_active_ms", "staff_ref", "is_super_admin",
}
```

Assert the private ingest request schema is write-only and absent from public
review/feed/profile response schemas. Run schema agreement against real
metadata in the isolated DB.

- [ ] **Step 4: Verify and commit**

```bash
cd backend
python -m pytest tests/test_telemetry_isolation.py \
  tests/test_postgrest_surface.py tests/test_openapi_contract.py \
  tests/test_schema_agreement.py -q
python -m ruff check app/ scripts/ tests/
cd ..
git add backend/tests/test_telemetry_isolation.py \
        backend/tests/test_postgrest_surface.py \
        backend/tests/test_openapi_contract.py \
        backend/tests/test_schema_agreement.py
git commit -m "test(telemetry): prove scoring payout and public isolation"
```

---

## Task 11: Full verification, release hygiene, and evidence

**Files:**
- Modify: `docs/RELEASE_HANDOFF.md` only if a runtime change in the same commit
  already requires it; never create a docs-only deployment candidate.
- Local-only updates: `.bluntly-autopilot/STATE.md`, `DECISIONS.md`,
  `BLOCKERS.md`, `RELEASE_EVIDENCE.md` — never stage.

- [ ] **Step 1: Run all local safe gates from a clean index**

```bash
git status --short
git diff --check
cd backend
python -m ruff check app/ scripts/ tests/
python -m pytest -q
python -m scripts.check_migration_safety --all
cd ..
npm run test:frontend
npx tsc --noEmit
npm run lint
npm run build
```

Expected: all commands exit 0; DB-only tests may skip locally only because the
guarded isolated database is absent. Treat warnings separately from failures
and record exact counts.

- [ ] **Step 2: Inspect the implementation against the approved constraints**

```bash
git diff --stat main...HEAD
git diff --check main...HEAD
git log --oneline main..HEAD
git status --short
git diff --cached --check
```

Confirm there is no raw IP/user-agent storage, no client identity/location/
timestamp field, no GET telemetry route, no score/payout import, no unbounded
retention delete, no session/credential file, and no local-only orchestration
artifact staged.

- [ ] **Step 3: Push the coherent candidate and monitor all required CI jobs**

Push the feature branch or fast-forward the authorized main branch according to
the repository's existing release flow. Inspect the actual current workflow job
names. Require production guard, backend no-DB, frontend, and isolated PostgreSQL
to be green. If any fail: inspect exact logs, reproduce where safe, add a failing
regression first, implement the smallest fix, rerun local gates, commit, push,
and monitor the replacement run. Do not increase timeouts to hide failures.

- [ ] **Step 4: Apply and verify the additive production migration**

Only after exact candidate CI is green, run the repository's approved guarded
production migration mechanism. Verify Alembic head is
`0041_reading_telemetry`, both tables/constraints/indexes/grants exist, existing
rows remain intact, and no broad production mutation occurred.

- [ ] **Step 5: Verify exact deployment convergence and production behavior**

Measure local HEAD, `origin/main`, CI head SHA, and Vercel production SHA. On
that exact SHA verify signed-out and signed-in review reading at desktop and
393px mobile: start plus sparse checkpoints, cookie lifetime/rotation, server
identity derivation, active/hidden/focus/idle behavior, scroll milestones,
successful interaction timing, bounded request count, and forced telemetry
failure without UX failure. Verify first-vote geography only with a reversible
new QA vote and restore the intended vote state afterward; never alter payouts.

- [ ] **Step 6: Verify privacy, retention, logs, and QA handoff**

Automate public response/HTML/network scans over `/`, `/feed`, `/search`, a
representative review, and a public profile. Require no telemetry identifiers,
`staff_ref`, `is_super_admin`, raw IP, user-agent, secret, or private metadata.
Inspect only final-deployment logs for unexpected 5xx, schema mismatch,
authorization exceptions, retention errors, or secret/payload leakage. Safely
run or inspect the scheduled retention path; do not delete in-window data.
Update the connected external QA handoff with exact SHA, CI run/totals,
migration, write-volume measurement, privacy/isolation evidence, desktop/mobile
acceptance, and truthful `NOT YET TESTED` independent-QA state.

- [ ] **Step 7: Reconcile next phases without activating decisioning**

Create read-only/offline research queries and reports that can run on whatever
data exists. If the sample is insufficient, record the exact minimum duration/
sample condition; do not manufacture correlations. Continue data-quality,
volume, replay/clamp, completeness, bias, and false-positive analyses that are
possible. Do not activate any score, threshold, priority, penalty, publication,
or payout change without later owner policy.

---

## Self-Review

- **Spec coverage:** Tasks 1–10 map every approved collection, identity,
  lifecycle, interaction, geography, retention, access, observability, privacy,
  and decision-isolation requirement to a failing behavior test and runtime
  change. Task 11 maps release and post-release evidence.
- **Placeholder scan:** every task names concrete behavior, commands, and expected
  results. The `photo` marker is deliberately schema-ready and unwired
  because the current product has no interactive photo action.
- **Type consistency:** `Checkpoint`, `ReaderIdentity`, `CastVoteResult`,
  `InteractionKind`, table/column names, limits, and route paths match the design
  specification and the interfaces consumed by later tasks.
- **Scope:** one coherent Phase 1 subsystem. Offline Phase 2+ analysis is limited
  to read-only preparation and cannot alter live decisioning.
