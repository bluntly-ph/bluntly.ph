# Review Integrity — Behavioral Signal Telemetry, Phase 1 (Design)

**Date:** 2026-09-03
**Status:** owner-approved architecture. Implementation plan:
`docs/superpowers/plans/2026-09-03-review-integrity-telemetry-phase-1.md`
**Scope:** collection only. No classifier. No change to any score, rank, queue
priority, publication decision, vote weight, fund share, or payout.

---

## 1. Why this exists

Three owner context documents (an independent research pass, a tracking
specification, and a conversation handoff) reach the same conclusion:

> Raw dwell time is **not** a usable authenticity signal today, but behavioural
> data cannot be reconstructed after the fact. Collect it now; keep it inert.

The evidence is genuinely mixed, and the design must respect that rather than
paper over it:

- Ilyas et al. (ETRA 2025, DOI 10.1145/3715669.3726846) find measurable
  eye-movement differences between AI-generated and human-authored text — enough
  to make reader behaviour scientifically worth instrumenting.
- Chen et al. (Frontiers in Psychology 2022, DOI 10.3389/fpsyg.2022.865702)
  tested this exact question on real product reviews and found **no** dwell-time
  difference on fake versus authentic comments. What *did* move dwell time was
  **review valence** — negative reviews attract far more attention.
- Yang et al. (Information Fusion 2026, DOI 10.1016/j.inffus.2026.104715), a
  survey of 211 studies, favours fusing heterogeneous evidence over trusting any
  single behavioural or linguistic detector.

Two consequences bind this design:

1. **The valence confound is real and must be measurable, not assumed away.**
   `star_rating_at_view` and `word_count_at_view` are snapshotted on every row so
   a Phase 3 analyst can control for the exact thing the literature says will
   otherwise be learned by mistake.
2. **The target is not "was this written by AI".** It is "is there credible
   evidence of a genuine product experience". AI-assisted prose can describe a
   real purchase; entirely human prose can be fabricated.

### The open item this closes

The repository already walked up to this decision and stopped:

- `backend/app/services/dashboard_service.py:10-16` — average read time is
  `None` because measuring it "needs a privacy decision that is the owner's to
  make rather than engineering's".
- `backend/app/api/v1/routes/users.py:229` — `average_read_seconds` is already
  `int | None` with `unavailable=("average_read_seconds",)`, built so it can
  carry a value the day that decision lands.
- `docs/IMPLEMENTATION_AUDIT.md:45-52` — logged as an open owner decision.

This design answers it, **and the answer for Phase 1 is that the field stays
`null`.** Collection is approved; publication is not.

---

## 2. Approved constraints (verbatim, non-negotiable)

- **C1.** Phase 1 covers **all** readers, signed-in and signed-out.
- **C2.** Signed-out readers use a **rotating random first-party pseudonymous
  identifier** — never a raw IP, fingerprint, email, user/staff/public ID, URL
  value, or cross-site identity.
- **C3.** Signed-in identity is **server-derived from the authenticated
  session**; no duplicated PII.
- **C4.** Active reading and scroll telemetry are **collection-only** and
  technically excluded from authenticity, trust, Wilson ranking, moderator
  priority, publication, vote weighting, Honesty Fund, payout, and penalties.
- **C5.** Conservative active time = visible **and** focused **and** recently
  active **and** review/body visible. Sparse local checkpoints. Coarse
  monotonic scroll milestones. Bounded writes.
- **C6.** Client telemetry is attacker-controlled: validate everything, derive
  server authority, rate-limit, and fail open for core UX.
- **C7.** Coarse geography only, from existing legitimate edge data. No GPS, no
  raw IP.
- **C8.** Additive migrations only. Bounded retention. No giant arbitrary JSON
  dump.

---

## 3. What already exists

| Capability | Location | Reused how |
|---|---|---|
| Edge geography → coarse location, no IP | `backend/app/services/request_geo.py` | `from_headers()` used verbatim for first-vote geography |
| Identity-free hourly aggregate + `NULLS NOT DISTINCT` UPSERT | `request_geo_buckets`, migration `0032` | Pattern copied for `review_first_vote_geo_buckets` |
| Identity-free per-review view counter | `review_view_buckets`, migration `0033` | Unchanged; its retention is repaired (§9) |
| Written trust model for unauthenticated ingest | `backend/app/api/v1/routes/traffic_ingest.py:11-25` | Precedent, extended in §8 |
| Redis → Postgres → open rate limiter | `backend/app/core/rate_limit.py` | `enforce_rate_limit(request, "reading_telemetry", ...)` |
| Server-derived session identity | `core/security.py::get_optional_user`, `lib/dal.ts`, `lib/session.ts` | Satisfies C3 with no new code |
| Leased, allow-listed scheduler | `backend/app/api/v1/routes/internal_cron.py` | `pii_retention` task carries the new sweeps |
| Set-based retention | `backend/app/services/retention_service.py` | Extended, batched (§9) |
| Wilson lower bound on weighted counts | `backend/app/services/ranking.py:37` | Reused as-is for confidence-adjusted voter frequency (§10) |
| Grant-based PostgREST lockdown + drift detection | migration `0029`, `scripts/check_invariants.py:144-158` | New tables asserted closed |
| ORM/schema drift guard | `backend/tests/test_schema_agreement.py` | Automatic once models are registered |

### Two live defects repaired here

1. **`review_view_buckets` retention is never executed.**
   `request_traffic_service.purge_expired_views` (`:230`) has **zero production
   callers**. Migration `0033` promises 90-day retention; nothing enforces it.
   View buckets accumulate indefinitely today.
2. **`request_geo_buckets` retention runs on an incidental path.**
   `purge_expired` is called only when a *new* bucket row is inserted
   (`request_traffic_service.py:86`). With stable geography and continuous
   traffic, hours pass with no purge. It works; it is not a schedule.

Both are fixed by moving retention into `retention_service.run_retention_sweep`,
which the daily `pii_retention` task already invokes at 03:00 Manila.

### What does not exist

No pseudonymous reader identity. No per-impression record (a counter cannot hold
duration). No client instrumentation of any kind — the repository contains no
`visibilitychange` handler, no `IntersectionObserver`, and no `sendBeacon`. No
link between a vote and the reading that preceded it.

**And one naming correction:** the moderator globe renders
`request_geo_buckets` — *request* counts by city. The context handoff describes
it as *vote* counts by city. Those are different measurements and this design
does not silently promote one into the other; §7 adds the real thing under an
honest name.

---

## 4. Architecture

### 4.1 Options considered

**A — Append-only event log, one row per checkpoint.** Highest fidelity; the
full interaction sequence survives. **Rejected:** row count scales with
checkpoints rather than impressions, needs its own aggressive retention, and at
100k views/day reaches ~22M rows inside the retention window. C8 says bounded;
this is the unbounded shape.

**B — One durable row per impression, monotonically UPSERTed. ADOPTED.** Sparse
client checkpoints merge into a single row with `GREATEST(existing, incoming)`
on every counter. Idempotent by construction: replayed, duplicated, or
out-of-order checkpoints are no-ops, and a counter can never decrease. The
trade-off is real and accepted: **the intra-session time series is lost** — we
keep final state, not the shape of the curve. Phase 1 asks "how much active
reading", not "in what rhythm". It is also the idiom this codebase already uses
twice (`0032`, `0033`).

**C — Single terminal write on `pagehide`.** Cheapest possible. **Rejected as
the sole mechanism:** `pagehide` is unreliable on iOS Safari and lost entirely
on tab kill, crash, or OOM. Systematically losing the longest sessions biases
the exact variable being measured.

**Adopted: B, bracketed by an immediate start checkpoint and C's terminal
flush.** Monotonic merge makes all three compose safely.

### 4.2 The start checkpoint

**A non-blocking start checkpoint fires immediately on mount** (`seq = 0`,
`active_ms = 0`, `wall_ms = 0`, `scroll_milestone = 0`).

This exists because a near-instant vote — the single most interesting event in
the entire fraud question — would otherwise have no session row to attach to.
The start checkpoint guarantees a **server-owned `started_at`** before any
interaction can occur.

Consequences, stated plainly:

- Every impression produces **exactly one row**, including sub-second bounces.
  Row count is now `1 × impressions`, not a fraction of it. §11 reflects this.
- Later checkpoints carry **cumulative** values, not deltas. A delta scheme
  would break the monotonic-merge idempotency that makes replay safe.
- The 16-checkpoint hard cap **includes the start**: start plus at most 15
  further writes per impression.
- It is fired with `keepalive` and its promise is never awaited. It cannot
  block paint, hydration, or interaction.

### 4.3 Active time — the exact predicate (C5)

`active_ms` accumulates **only while all of the following hold**:

1. `document.visibilityState === "visible"`
2. `document.hasFocus()`
3. last user input within `IDLE_MS = 30_000` — reset by `pointermove`,
   `pointerdown`, `keydown`, `wheel`, `scroll`, `touchstart`

`body_active_ms` additionally requires the review body (`#review-body`) to be
intersecting the viewport, via `IntersectionObserver(threshold: 0)`.

Accumulation uses `performance.now()`, never `Date.now()`, so a system clock
adjustment cannot inflate a session.

**`IDLE_MS = 30_000` is deliberately conservative and will under-count a reader
who does not move for 40 seconds.** That is the intended direction of error. To
keep the loss measurable rather than silent, `wall_ms` (elapsed since mount,
capped) is stored alongside, so an analyst can see exactly how much the idle
rule discarded and whether the rule is itself a confound.

### 4.4 Scroll (C5)

`scroll_milestone ∈ {0, 25, 50, 75, 100}` — the deepest bucket the body's
read-through fraction has ever reached. Monotonic client-side, `GREATEST`-merged
server-side. A continuous percentage would be a higher-resolution behavioural
fingerprint for no analytical gain.

### 4.5 Checkpoint schedule

| Trigger | `seq` | Notes |
|---|---|---|
| Mount | 0 | Immediate, non-blocking. Always fires. |
| `active_ms` crosses 10s | 1 | |
| 30s | 2 | |
| 60s | 3 | |
| 120s, then every 120s | 4… | |
| `visibilitychange → hidden`, `pagehide` | next | `navigator.sendBeacon`, falling back to `fetch(..., {keepalive:true})` |

Hard stops: `MAX_SESSION_MS = 1_800_000` (30 min) or 16 checkpoints, whichever
comes first.

**Floor:** no checkpoint after the start is sent below `MIN_ACTIVE_MS = 1_000`
of accumulated active time. A sub-second bounce therefore costs exactly one
write, and its row reads `active_ms = 0, checkpoints = 1` — which is itself the
bounce signal, recorded rather than inferred.

---

## 5. Identity model (C2, C3)

Two columns, **exactly one non-null**, enforced by the database:

```sql
reader_kind  reader_kind NOT NULL,        -- 'anon' | 'user'
reader_ref   uuid NULL REFERENCES users(id) ON DELETE CASCADE,
anon_ref     uuid NULL,                   -- opaque; no FK, no preimage

CONSTRAINT ck_reading_reader_user CHECK ((reader_kind = 'user') = (reader_ref IS NOT NULL)),
CONSTRAINT ck_reading_reader_anon CHECK ((reader_kind = 'anon') = (anon_ref  IS NOT NULL))
```

Properties, each a database constraint rather than a promise:

- **No row can carry both.** There is therefore no direct account-to-pseudonym
  linkage key in the database. This satisfies "no duplicated PII" (C3) without
  overstating privacy: an authorized analyst could still infer correlations
  from time, review, and coarse-country patterns, so raw access remains
  restricted.
- **`ON DELETE CASCADE`** makes account-deletion erasure automatic. No bespoke
  code, nothing to forget.
- A single polymorphic column was rejected: it cannot carry the foreign key,
  cannot cascade, and makes every future query ambiguous about what it joins.

### The pseudonym

Cookie `bluntly_rid`: `httpOnly`, `Secure` in production, `SameSite=Lax`,
`Path=/`, `Max-Age=86400`, value `crypto.randomUUID()`.

- **Absolute 24-hour lifetime, no sliding renewal.** A reader returning tomorrow
  is a new pseudonym. This bounds how long any behavioural trail can be linked.
- **Cleared on every identity boundary** — in `createSession` and
  `destroySession` (`lib/session.ts`), so signing in or out breaks the chain.
- **`httpOnly` is load-bearing.** Client JavaScript never reads it, so it can
  never enter a payload, a URL, or a third-party request. The client body
  carries no identity field at all; the server reads the cookie.
- Derived from nothing: not an IP, not a hash of an IP, not a fingerprint, not
  `users.id`, not `user_id`, not `staff_ref`, not a URL value. CSPRNG output
  with no preimage.

### Resolution order (server)

| Condition | Result |
|---|---|
| Valid `Authorization: Bearer` via `get_optional_user` | `reader_kind='user'`, `reader_ref=user.id`. **`X-Reader-Anon` discarded, never stored.** |
| No/invalid bearer, valid `X-Telemetry-Key`, valid `X-Reader-Anon` UUID | `reader_kind='anon'`, `anon_ref=<uuid>` |
| Anything else | `401`, write nothing |

---

## 6. Schema

Migration `0041_reading_telemetry`, `down_revision = "0040_role_admin_audit_enum"`.
Additive only (C8): one enum type, two tables. No column added to, and no
constraint changed on, any existing table.

### 6.1 `review_reading_sessions`

```sql
CREATE TYPE reader_kind AS ENUM ('anon', 'user');

CREATE TABLE review_reading_sessions (
    id               bigserial PRIMARY KEY,
    impression_id    uuid        NOT NULL,   -- client-generated; grouping + idempotency ONLY
    review_id        uuid        NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,

    reader_kind      reader_kind NOT NULL,
    reader_ref       uuid        NULL REFERENCES users(id) ON DELETE CASCADE,
    anon_ref         uuid        NULL,

    -- SERVER CLOCK ONLY. The client never sends an absolute timestamp.
    started_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at     timestamptz NOT NULL DEFAULT now(),

    -- Monotonic cumulative counters, milliseconds. GREATEST-merged.
    active_ms        integer     NOT NULL DEFAULT 0,
    body_active_ms   integer     NOT NULL DEFAULT 0,
    wall_ms          integer     NOT NULL DEFAULT 0,

    scroll_milestone smallint    NOT NULL DEFAULT 0,
    checkpoints      smallint    NOT NULL DEFAULT 0,   -- server-counted, caps at 16
    max_seq          integer     NOT NULL DEFAULT 0,   -- replay fence
    clamped          boolean     NOT NULL DEFAULT false,

    -- First-occurrence-wins interaction timing. CLIENT-ASSERTED — named so.
    vote_client_after_ms    integer NULL,
    report_client_after_ms  integer NULL,
    comment_client_after_ms integer NULL,
    share_client_after_ms   integer NULL,
    photo_client_after_ms   integer NULL,
    outlink_client_after_ms integer NULL,

    -- SERVER-STAMPED from the vote route. The trustworthy half.
    first_vote_at           timestamptz NULL,
    active_ms_at_first_vote integer     NULL,

    -- Coarse geography: COUNTRY ONLY. See §6.3.
    country          char(2)  NULL,

    -- Confound controls, server-derived, snapshotted at write time.
    word_count_at_view  smallint NULL,
    star_rating_at_view smallint NULL,
    device_class        smallint NOT NULL DEFAULT 0,   -- 0 unknown 1 phone 2 tablet 3 desktop

    CONSTRAINT ck_reading_reader_user CHECK ((reader_kind = 'user') = (reader_ref IS NOT NULL)),
    CONSTRAINT ck_reading_reader_anon CHECK ((reader_kind = 'anon') = (anon_ref  IS NOT NULL)),
    CONSTRAINT ck_reading_scroll      CHECK (scroll_milestone IN (0,25,50,75,100)),
    CONSTRAINT ck_reading_device      CHECK (device_class BETWEEN 0 AND 3),
    CONSTRAINT ck_reading_ms_signs    CHECK (active_ms >= 0 AND body_active_ms >= 0 AND wall_ms >= 0),
    CONSTRAINT ck_reading_body_le_act CHECK (body_active_ms <= active_ms),
    CONSTRAINT ck_reading_duration_cap CHECK (active_ms <= 1800000 AND body_active_ms <= 1800000
                                               AND wall_ms <= 1800000),
    CONSTRAINT ck_reading_checkpoint_cap CHECK (checkpoints BETWEEN 1 AND 16 AND max_seq >= 0),
    CONSTRAINT ck_reading_interaction_cap CHECK (
      (vote_client_after_ms IS NULL OR vote_client_after_ms BETWEEN 0 AND 1800000) AND
      (report_client_after_ms IS NULL OR report_client_after_ms BETWEEN 0 AND 1800000) AND
      (comment_client_after_ms IS NULL OR comment_client_after_ms BETWEEN 0 AND 1800000) AND
      (share_client_after_ms IS NULL OR share_client_after_ms BETWEEN 0 AND 1800000) AND
      (photo_client_after_ms IS NULL OR photo_client_after_ms BETWEEN 0 AND 1800000) AND
      (outlink_client_after_ms IS NULL OR outlink_client_after_ms BETWEEN 0 AND 1800000) AND
      (active_ms_at_first_vote IS NULL OR active_ms_at_first_vote BETWEEN 0 AND 1800000)
    )
);

CREATE UNIQUE INDEX uq_reading_impression      ON review_reading_sessions (impression_id);
CREATE INDEX        ix_reading_started_at      ON review_reading_sessions (started_at);
CREATE INDEX        ix_reading_review_started  ON review_reading_sessions (review_id, started_at);
CREATE INDEX        ix_reading_reader_review   ON review_reading_sessions (reader_ref, review_id)
                                               WHERE reader_ref IS NOT NULL;
```

**`device_class` is derived server-side from the request `User-Agent` and is
never accepted from the client payload.** The raw User-Agent is **never
persisted** — only the four-value bucket. A client-supplied device field would
be one more attacker-controlled column for no gain, and storing the raw string
would add a fingerprinting surface this design exists to avoid. It is
`NOT NULL DEFAULT 0` because an unparseable or absent User-Agent is a legitimate
outcome ("unknown"), not a missing value.

`word_count_at_view` and `star_rating_at_view` are **snapshotted rather than
joined** because a review can be edited (`current_version`, `review_versions`),
and an engagement residual computed against the current text of an edited review
would compare a reader's behaviour to words they never saw.

**No JSONB anywhere.** Every field is typed, bounded, and named. C8's "no giant
arbitrary JSON dump" is enforced by there being nowhere to put one.

### 6.2 `review_first_vote_geo_buckets`

```sql
CREATE TABLE review_first_vote_geo_buckets (
    id               bigserial PRIMARY KEY,
    review_id        uuid        NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    bucket_start     timestamptz NOT NULL,          -- UTC hour
    country          char(2)     NULL,
    region           varchar(64) NULL,
    city             varchar(128) NULL,
    first_vote_count bigint      NOT NULL DEFAULT 0,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_review_first_vote_geo
    ON review_first_vote_geo_buckets (review_id, bucket_start, country, region, city)
    NULLS NOT DISTINCT;
CREATE INDEX ix_review_first_vote_geo_start
    ON review_first_vote_geo_buckets (bucket_start);
```

**The name is the specification.** This counts **first-time votes only** — the
creation of a `ReviewVote` row. A same-direction retry increments nothing; a
direction change (up → down) increments nothing. Without that rule the number
would be "vote button presses by place", which a single user toggling their vote
could inflate arbitrarily, and calling that "votes by city" would be a lie in a
panel moderators use to reason about coordination.

**No voter column. No IP.** A row says "this review received 12 first-time votes
from Cebu in this hour" and cannot say by whom — the same property that makes
migration `0032` aggregate analytics rather than tracking.

`NULLS NOT DISTINCT` is not decoration: under the default `NULLS DISTINCT`, two
country-only rows for the same hour would never conflict, every vote would
insert a new row, and the "aggregate" would grow exactly like a log. This is the
bug migration `0032:59-67` documents.

### 6.3 Why country only on the impression row (C7)

`request_geo_buckets` is defensible precisely because it carries geography **with
no identity attached**. Placing `city` beside a reader pseudonym creates a coarse
location trail per pseudonym — a materially different posture that "coarse
geography only" does not license.

A country holds millions of people and the pseudonym dies in 24 hours; that pair
is not a locator. City-level analysis continues where it already happens: in the
identity-free hourly aggregates.

---

## 7. Ingestion contract

### 7.1 Two endpoints, two different jobs

| | Public (browser-facing) | Private (backend) |
|---|---|---|
| Path | `POST /api/telemetry` (Next Route Handler) | `POST /api/v1/internal/reading-telemetry` |
| Purpose | fail-open UX shield | real validation and enforcement |
| Success | `204` | `204` |
| Invalid body | **`204`** | `422` |
| Unauthenticated | **`204`** | `401` |
| Rate limited | **`204`** | `429` |
| Backend unreachable | **`204`** | — |
| `GET` | `405` (no handler) | **no route exists** |

**The public route always returns 204.** A reader whose page rendered perfectly
must never learn that a counter did not increment, and a beacon cannot act on an
error anyway. **The private route returns real status codes** so that
monitoring, tests, and the export tooling can tell a rejected payload from an
accepted one — a backend that answers 204 to everything is a backend whose
validation cannot be observed.

Neither endpoint exposes a `GET`. Nothing reads this data back over HTTP in
Phase 1 (§10).

### 7.2 Client payload

Durations only. No absolute timestamps, no identity, no URL values, no device
field.

```jsonc
{
  "impression_id":   "3f2a...-uuid-v4",
  "review_id":       "9c11...-uuid",
  "seq":             3,
  "active_ms":       41210,
  "body_active_ms":  38900,
  "wall_ms":         61004,
  "scroll_pct":      75,
  "vote_after_ms":    null,
  "report_after_ms":  null,
  "comment_after_ms": null,
  "share_after_ms":   null,
  "photo_after_ms":   null,
  "outlink_after_ms": null
}
```

Unknown fields are **rejected** (`extra="forbid"`), matching
`test_request_distribution.test_unknown_fields_cannot_be_mass_assigned`.

### 7.3 The Next Route Handler

`app/api/telemetry/route.ts` is where identity is derived, because it is the only
place that sees both cookies and the visitor's edge headers.

1. Read `bluntly_rid`; if absent or malformed, mint one and `Set-Cookie` it on
   the 204 response — usable from checkpoint 0 of the very first impression.
2. Read `bluntly_session`; if present, attach `Authorization: Bearer <token>`.
3. Normalise `x-vercel-ip-country` → `country`, reusing the `clean()` shape
   already in `lib/traffic-beacon.ts`.
4. Forward `user-agent` so the backend can derive `device_class`.
5. Forward to the private endpoint with `X-Reader-Anon` and `X-Telemetry-Key`.
6. **Always answer 204**, whatever upstream did.

It is a dedicated handler rather than the generic `/api/bff/[...path]` pipe on
purpose: that pipe is documented as "a dumb pipe… no response reshaping", strips
`cookie` deliberately, and giving it identity-derivation duties would change its
contract for every route that uses it.

### 7.4 Idempotency, replay, and clamping

One statement, in the shape `request_traffic_service.record` already uses:

```sql
INSERT INTO review_reading_sessions (...) VALUES (...)
ON CONFLICT (impression_id) DO UPDATE SET
    active_ms        = GREATEST(review_reading_sessions.active_ms,        EXCLUDED.active_ms),
    body_active_ms   = GREATEST(review_reading_sessions.body_active_ms,   EXCLUDED.body_active_ms),
    wall_ms          = GREATEST(review_reading_sessions.wall_ms,          EXCLUDED.wall_ms),
    scroll_milestone = GREATEST(review_reading_sessions.scroll_milestone, EXCLUDED.scroll_milestone),
    vote_client_after_ms = COALESCE(review_reading_sessions.vote_client_after_ms,
                                    EXCLUDED.vote_client_after_ms),
    -- ... identical COALESCE for report/comment/share/photo/outlink
    checkpoints      = review_reading_sessions.checkpoints + 1,
    max_seq          = EXCLUDED.max_seq,
    clamped          = review_reading_sessions.clamped OR EXCLUDED.clamped,
    last_seen_at     = now()
WHERE review_reading_sessions.review_id   =  EXCLUDED.review_id
  AND review_reading_sessions.reader_kind =  EXCLUDED.reader_kind
  AND review_reading_sessions.reader_ref  IS NOT DISTINCT FROM EXCLUDED.reader_ref
  AND review_reading_sessions.anon_ref    IS NOT DISTINCT FROM EXCLUDED.anon_ref
  AND review_reading_sessions.max_seq     <  EXCLUDED.max_seq
  AND review_reading_sessions.checkpoints <  16;
```

| Attack / accident | Defeated by |
|---|---|
| Duplicate delivery (identical payload) | `max_seq < EXCLUDED.max_seq` is false → zero rows; `GREATEST` of equal values is a no-op anyway |
| Out-of-order delivery (stale checkpoint) | same `max_seq` fence, and `GREATEST` even if `seq` were forged upward |
| Cross-reader replay (captured `impression_id`) | reader predicates match zero rows; response is still 204, so probing learns nothing |
| Cross-review replay | `review_id` predicate |
| Checkpoint pumping | `checkpoints < 16`, enforced **in the database**, independent of client and limiter |

**Timestamp sanity.** The client sends no absolute time, so there is nothing to
backdate. Before the statement runs, server-side:

- `active_ms ← min(active_ms, MAX_SESSION_MS)`
- on update: `active_ms ← min(active_ms, elapsed_since_started_at + 5_000)` — a
  reader cannot have accumulated more active time than has elapsed since the
  server first saw the impression, plus skew tolerance
- `body_active_ms ← min(body_active_ms, active_ms)`
- `wall_ms ← min(wall_ms, MAX_SESSION_MS)`
- `scroll_pct` is rejected by the typed request contract unless it is exactly
  one of `0,25,50,75,100`; the database repeats the same constraint
- any clamp sets `clamped = true`

`clamped` matters: a poisoned or buggy row is **visible in the dataset rather
than silently normalised**. The `CHECK` constraints are the last line — even a
bug in the clamping code cannot land an illegal row.

### 7.5 Rate limits and fail-open (C6)

Two independent bounds, because they fail differently:

- **Per caller:** `enforce_rate_limit(request, "reading_telemetry",
  max_requests=60, window_seconds=60)` — reuses the existing
  Redis → Postgres → open limiter and its `x-forwarded-for` keying.
- **Per impression:** `checkpoints < 16` in SQL. A distributed flooder that
  defeats the IP limiter still cannot inflate one impression.

| Failure | Reader sees | Data |
|---|---|---|
| Backend 5xx | 204 | lost silently |
| Rate limited | 429 upstream → **204** to browser | not written |
| Invalid payload | 422 upstream → **204** to browser | not written |
| Both limiter stores down | limiter opens (existing behaviour, logs `warning`) | written |
| `TELEMETRY_INGEST_KEY` unset | 204 to browser | anon path writes nothing; `warning` logged |
| Cookies blocked / JS off | nothing sent | no row; page renders normally |

No telemetry failure can render an error, block a paint, or fail a vote.

### 7.6 Threat model — what the shared key does and does not buy

`X-Telemetry-Key` is a server-only secret held in the Next runtime environment.
It **prevents an attacker from bypassing our edge and POSTing directly to
`/api/v1/internal/reading-telemetry`**, which matters because `vercel.json`
rewrites `/api/v1(/.*)?` straight to the backend service and that path is
reachable from the public internet.

**It does not make browser telemetry trustworthy, and nothing can.** Any reader
can open developer tools, read the payload our own client sends, and replay it
through `/api/telemetry` — which will happily attach the key on their behalf.
That is inherent to client-side measurement, not a gap in this design.

Poisoning resistance therefore comes from five independent mechanisms, none of
which is the key:

1. **Server derivation.** Identity, `started_at`, `last_seen_at`,
   `device_class`, `country`, `word_count_at_view`, `star_rating_at_view`,
   `first_vote_at`, and `active_ms_at_first_vote` are all derived server-side. A
   forged payload cannot touch any of them.
2. **Database constraints.** Illegal identity combinations, out-of-range
   milliseconds, and off-grid scroll values cannot be stored at all.
3. **Elapsed-time clamps.** Claimed active time is bounded by wall-clock time
   the server itself observed, so "I read for 30 minutes" three seconds after
   the start checkpoint is clamped and flagged.
4. **Rate limits.** Per-caller, on the existing limiter.
5. **Per-impression caps.** 16 checkpoints, enforced in SQL.

And the decisive containment: **the data influences nothing** (C4, §8). The
worst outcome of successful poisoning is a noisier research dataset — not a
changed score, ranking, moderation decision, or payout. That is the property
that makes the residual risk acceptable, and §12 turns it into tests.

---

## 8. Scoring and payout isolation (C4)

Telemetry is excluded from every one of the following, and the exclusion is
enforced structurally rather than by convention:

| Surface | Module | How exclusion is enforced |
|---|---|---|
| Wilson ranking | `services/ranking.py`, `services/vote_service.py` | static import assertion + behavioural equality test |
| Trust / reputation / stage | `services/trust.py`, `services/trust_service.py` | same |
| Product trust rating | `services/trust_rating_service.py` | same |
| Moderator priority & queue | `services/admin_overview_service.py`, `services/referral_service.py`, `services/fraud_service.py` | same, plus `QueueSignals` field freeze |
| Publication | `services/referral_service.py` | same |
| Vote weighting | `services/trust.py::gate_vote_weight` | same |
| Honesty Fund | `services/honesty_fund_service.py` | same, plus identical-payout test |
| Payout / commission / earnings | `services/payout_service.py`, `services/commission_service.py`, `services/earnings.py` | same |
| Reviewer-facing publication | `services/dashboard_service.py` | `average_read_seconds` pinned `null` |

**Direction of dependency is the whole discipline.** The vote route *writes*
telemetry (§9.1); telemetry is never *read* by anything that computes a score or
moves money. Phase 1 ships **no HTTP read path for this data at all** — not
moderator-gated, not super-admin-gated. `traffic_ingest.py:17` already states the
principle: "nothing here reads back, so it cannot be used to learn anything."

Analysis runs through `backend/scripts/export_reading_telemetry.py`, a read-only
owner-run CSV exporter in the same idiom as `scripts/check_invariants.py`.

**`average_read_seconds` stays `null` through Phase 1.** The research handoff
(§12) argues that exposing reading time to reviewers converts it into an
optimisation target — longer reviews, manufactured controversy, friends parking
tabs. The field and its `unavailable[]` entry remain exactly as they are, pinned
by a test.

---

## 9. Server-authoritative writes

### 9.1 Vote timing

In `backend/app/api/v1/routes/reviews.py::vote_review`, **after** `cast_vote`
returns:

```python
result = vote_service.cast_vote(db, review, user, payload.vote)
reading_telemetry_service.note_vote(db, result.review.id, user.id)  # never raises
if result.created:
    request_traffic_service.record_first_vote_geo(
        db, result.review.id, from_headers(request.headers))       # never raises
```

`note_vote` sets `first_vote_at = now()` and `active_ms_at_first_vote =
<stored active_ms>` on that reader's most recent open impression for that
review, `COALESCE`-guarded so only the first vote stamps it. It runs in its own
transaction, swallows every exception, and does nothing if no impression exists.

`cast_vote` changes its return type from `Review` to a frozen
`CastVoteResult(review: Review, created: bool)`. The route is the only call site
that uses the return value; the two call sites in
`backend/tests/test_ranking_simulation.py` (`:284`, `:386`) ignore it and are
unaffected.

**Why touch a money-adjacent route at all.** "Active reading before the vote" is
the highest-value field in the dataset for the fraud question and the one field
that cannot be reconstructed later. The vote's outcome, weight, and Wilson
contribution are computed before these lines and are not re-read after them.

**Why `created` gates the geo write.** See §6.2 — counting retries and direction
changes would let one user inflate a city's number at will.

### 9.2 Retention (C8) — batched, bounded, idempotent, observable

`retention_service.run_retention_sweep` gains three sweeps. Each is a bounded
loop, not one unbounded `DELETE`:

```python
RETENTION_DAYS       = 90
RETENTION_BATCH      = 5_000    # rows per statement
MAX_BATCHES_PER_RUN  = 40       # 200_000 rows per scheduled execution

DELETE FROM <table>
 WHERE id IN (SELECT id FROM <table>
               WHERE <time_column> < :cutoff
               ORDER BY id
               LIMIT :batch)
```

Properties:

- **Bounded per execution.** At most 200,000 rows per table per run. Serverless
  request duration is never the binding constraint.
- **Idempotent.** Re-running deletes the next slice. A retry after a failure
  resumes rather than restarting; there is no cursor to corrupt because the
  predicate is the cutoff itself.
- **Safe to catch up.** Leftovers past the ceiling are picked up by the next
  day's run. The cutoff is recomputed each run, so a multi-day outage
  self-heals.
- **Observable.** Returns `{"reading_sessions": n, "review_view_buckets": n,
  "request_geo_buckets": n, "first_vote_geo_buckets": n, ...}`, which
  `internal_cron._pii_retention` already sums into `processed`. When a table
  hits `MAX_BATCHES_PER_RUN` a `warning` is logged naming the table, so a
  growing backlog is visible rather than silent.
- **`DELETE … WHERE id IN (SELECT … LIMIT)`** rather than a bare `LIMIT` because
  PostgreSQL does not accept `LIMIT` on `DELETE`.

Retention is **90 days**, matching `request_geo_buckets`, `review_view_buckets`,
and `dashboard_service.RANGES`. Account deletion is handled by foreign-key
cascade.

This repairs both defects in §3: `review_view_buckets` gains its first real
retention, and `request_geo_buckets` gains a schedule.

---

## 10. What this enables, and what it deliberately does not build

### Vote timing
Join `review_votes` to `review_reading_sessions` on `(review_id, reader_ref)`
and compare `review_votes.created_at` against `started_at`, `first_vote_at`, and
`active_ms_at_first_vote`. The handoff's framing question — "a vote after 500 ms
means something different from a vote after 25 seconds of active reading" —
becomes a query, with no classifier and no new model. Burstiness already has its
primitive in `ranking.velocity_exceeded` (`ranking.py:91`).

### Voter ↔ reviewer relationships, without a stored social graph
**No edge table is created.** The relationship is a derived query over a bounded
window — the posture `fraud_service` already takes ("computed on read… bounded
queries"):

```sql
WITH recent AS (
  SELECT id FROM reviews
   WHERE author_id = :author AND published_at IS NOT NULL AND is_removed = false
   ORDER BY published_at DESC LIMIT :window          -- 20-30 per the tracking spec
)
SELECT rv.voter_id, count(*) AS voted, (SELECT count(*) FROM recent) AS eligible
  FROM review_votes rv JOIN recent ON recent.id = rv.review_id
 GROUP BY rv.voter_id
```

Confidence-adjust with **`ranking.wilson_lower_bound(voted, eligible)` exactly as
it already exists** — the direct answer to the handoff's "a voter at 4/4 should
not automatically outrank a suspicious voter at 96/100". No new mathematics, no
new table, no graph that grows without bound, and nothing persisted that the
platform did not already record as votes.

Phase 1 ships the data and the query shape. It does **not** ship a moderator
panel for it; that is a Phase 2 product decision.

### Geographic-temporal analysis
Aggregate only:
- `review_first_vote_geo_buckets` — first-time votes by city per hour per
  review, no voter identity;
- correlated against `request_geo_buckets` — traffic by city per hour — to
  separate "this city votes a lot" from "this city merely visits a lot";
- `review_reading_sessions.country` for coarse cohort normalisation.

**Deliberately not built:** per-voter city attribution, any join from a person to
a place, any persisted co-occurrence matrix, any cluster-membership label.
Detecting coordination is an aggregate question; tracking a person is not.

### Not built, and not by accident
No classifier. No risk score. No "AI probability". No engagement residual. Those
are Phases 2–4, and the tracking spec is explicit that they come only after
baselines and back-testing against real outcomes (moderator rejection, confirmed
fraud, verified genuine experience, post-approval reversal).

---

## 11. Write volume

Every impression produces exactly one row, because the start checkpoint always
fires (§4.2).

| Reader | POSTs (checkpoints) | Rows |
|---|---|---|
| Bounce < 1s | 1 — start only | 1 |
| Short 1–30s | 2–3 — start, [10s], flush | 1 |
| Typical ~35s active | 4 — start, 10s, 30s, flush | 1 |
| Long 5 min active | 7 — start, 10, 30, 60, 120, 240, flush | 1 |
| Adversarial | 16 (hard cap) | 1 |

Mix model — 30% bounce, 50% short (avg 2.5), 18% medium (avg 4.5), 2% long (7):

```
POSTs per view = 0.30(1) + 0.50(2.5) + 0.18(4.5) + 0.02(7)
               = 0.30 + 1.25 + 0.81 + 0.14
               = 2.50
```

| Volume | Rows | POSTs | SQL statements | Storage (heap + index) |
|---|---|---|---|---|
| 1 view | 1 | 2.5 | 2.5 | ~320 B |
| 1,000 views | 1,000 | ~2,500 | ~2,500 | **~320 KB** |
| 100,000 views | 100,000 | ~250,000 | ~250,000 | **~32 MB** |

Row width ≈ 200 B including tuple overhead; four indexes ≈ 120 B ⇒ ~320 B/row
all-in.

**Steady state is the number that matters.** At a sustained 100k views/day,
90-day retention holds ~9.0M rows ≈ **~2.9 GB**. At 100k views/month it is
~96 MB. The retention ceiling of 200k rows/run (§9.2) gives 2× headroom over the
~100k rows/day that age out at that volume.

**Throughput:** 250k POSTs per 100k views ≈ 2.9 writes/sec spread over a day,
~29/sec at a 10× peak. Roughly 4× the current traffic-beacon load against the
Supabase **transaction** pooler (`db/session.py:12-15`) — comfortable, but the
largest new write load this repository has added.

**Tuning lever, and its limit.** Moving the first periodic checkpoint from 10s to
20s and dropping the 60s step takes a typical impression from 4 POSTs to 3
(≈20% fewer requests). **Row count cannot be tuned down** — the start checkpoint
fixes it at one per impression, which is the price of correction #1 and is paid
knowingly.

The existing traffic beacon (1 POST → 2 UPSERTs per page request) is unchanged
and additional to all of the above.

---

## 12. Interaction marker boundary

Six existing client components must tell `ReadingTelemetry` that an interaction
happened. The boundary is a **small typed CustomEvent** — no global object, no
`window.__telemetry`, no context provider threaded through server components.

`lib/reading-telemetry-events.ts`:

```ts
export const TELEMETRY_EVENT = "bluntly:review-interaction";
export type InteractionKind =
  "vote" | "report" | "comment" | "share" | "photo" | "outlink";
export type InteractionDetail = { reviewId: string; kind: InteractionKind };
export function markInteraction(reviewId: string, kind: InteractionKind): void;
```

- `markInteraction` dispatches a namespaced `CustomEvent` on `window` and is a
  no-op during SSR.
- `ReadingTelemetry` subscribes in `useEffect` and **removes the listener in the
  cleanup function** — required, because the review page can unmount on client
  navigation and a leaked listener would attribute a later review's interactions
  to a dead impression.
- The handler filters on `detail.reviewId === props.reviewId`, so two review
  surfaces on one page cannot cross-talk.
- First-occurrence-wins is enforced client-side in a ref **and** server-side by
  `COALESCE`. Two independent guarantees, because the client one can be bypassed.

| Kind | Emitter | Trigger point |
|---|---|---|
| `vote` | `components/review/ReviewVoteBar.tsx` | successful non-remove vote response |
| `report` | `components/review/ReportDialog.tsx` | `setState("done")` |
| `comment` | `components/review/CommentThread.tsx` | successful comment POST, before `onPosted` |
| `share` | `components/review/ShareButton.tsx` | successful `navigator.share` or clipboard write |
| `share` | `components/review/ReviewOverflowMenu.tsx` | successful `copyLink` |
| `outlink` | `components/review/ReadingTelemetry.tsx` | delegated `click` on `a[data-telemetry-outlink]` |
| `photo` | **none in Phase 1** | see below |

**Outbound links use event delegation** rather than a new client component,
because the three "Buy it here" anchors live in server components
(`ReviewDetail.tsx` ×2, `ReviewAside.tsx` ×1). They gain a
`data-telemetry-outlink` attribute; `ReadingTelemetry` attaches one delegated
listener on `document` and removes it on cleanup. Zero new client components.

**`photo` has no emitter in Phase 1, and this is deliberate rather than
unfinished.** The review page renders images through non-interactive
`next/image` — there is no lightbox, no gallery, and no photo-open control to
instrument. The `InteractionKind` union includes `photo` and the column exists so
that a future photo viewer needs no schema or contract change; until then
`photo_client_after_ms` is `NULL` on every row, and a test asserts it.

---

## 13. Privacy disclosure

`app/privacy/page.tsx` gains one plain-language item under "What we collect" and
one under "Data retention and security". The wording states what happens, in
ordinary words. It makes **no claim about a legal basis and no claim of
regulatory compliance** — that is the owner's to assert, not engineering's.

> **What we collect** — *Reading activity* — how long a review page is actively
> open, how far you scroll it, and whether you voted, commented, shared, or
> reported while reading. For signed-out readers this uses a random identifier
> stored in a first-party cookie that changes at least every 24 hours and is not
> linked to any account.

> **Data retention and security** — Reading-activity records are deleted after
> 90 days.

The existing policy already discloses "basic device, log, and analytics
information needed to run and secure the service". These lines make the specific
practice legible rather than relying on that general phrase.

---

## 14. Open decisions this design does not make

These remain the owner's, and none of them blocks implementation. Conservative
defaults are already in the design.

1. **Whether the disclosure copy in §13 is sufficient**, and what lawful basis to
   assert. *Default:* ship §13 as written, assert nothing.
2. **Cookie consent posture.** `bluntly_rid` is first-party, `httpOnly`, 24-hour.
   Whether an EU-facing consent gate is required depends on the audience the
   owner intends to serve. *Default:* no banner.
3. **Retention length.** *Default:* 90 days. A cross-season back-test may want
   180–365, which is a different privacy argument and ~4× the storage in §11.
4. **Whether `average_read_seconds` ever ships.** *Default:* `null` through
   Phases 1–3, pinned by a test.
5. **Whether staff reading belongs in the dataset.** *Default:* collect (a reader
   is a reader) and exclude at analysis time by joining `users.role`.
   Suppressing collection for staff is equally defensible and equally cheap.
6. **Edge-header trust.** §6.2 assumes Vercel overwrites client-supplied
   `x-vercel-ip-*` headers at the edge, so a forged header through the BFF cannot
   poison a bucket. This is documented platform behaviour but unverified for this
   deployment; it is checkable in one call against the existing
   `GET /api/v1/admin/analytics/geo-probe` (`admin_analytics.py:51`) with a
   forged header. Until verified, first-vote geography is best-effort
   operational data, which is what it is already labelled as.

---

## 15. Acceptance

Phase 1 is **not** accepted because telemetry appears. It is accepted when:

- `tests/test_telemetry_isolation.py` is green — no scoring or payout module
  references telemetry;
- Wilson score, reputation, trust stage, helpfulness ratio, fraud signals, and
  Honesty Fund payouts are **byte-identical** with telemetry present, with
  telemetry absent, and with adversarially extreme telemetry;
- `average_read_seconds` is still `null` and still named in `unavailable[]`;
- the moderator queue's Score and Priority are unchanged;
- no `GET` route exposes any telemetry field;
- `review_reading_sessions` and `review_first_vote_geo_buckets` are unreadable
  by `anon` and `authenticated`;
- `scripts/check_invariants.py --strict` reports zero rows carrying two
  identities and zero rows past retention;
- `review_view_buckets` retention executes for the first time.
