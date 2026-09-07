import assert from "node:assert/strict";
import test from "node:test";

import {
  accountAgeLabel,
  authorTrustStats,
  engagementFor,
  paginate,
  priorityOf,
  queueRows,
  relativeAge,
  reportCountFor,
  reviewIdLabel,
} from "../../components/admin/review-queue-model.ts";

/**
 * A queue card as `GET /admin/review-queue` actually returns it — every field
 * the frontend `QueueItem` type declares, so a model function that reaches for
 * a field these tests do not set still finds one, and a model function that
 * reaches for the WRONG field is caught by the distinct values.
 */
const item = (overrides = {}) => ({
  review: {
    id: "11111111-2222-3333-4444-555555555555",
    title: "Solid Powerbank but gets warm",
    discussion: "Basta Anker, quality!",
    verdict: "yes_absolutely",
    star_rating: 4,
    verification_status: "verified",
    has_receipt: true,
    created_at: "2026-09-08T12:00:00.000Z",
    review_id: "rev_a1b2c3d4e5",
    photo_url: "https://example.test/photo.jpg",
    wilson_score: "0.8412",
    helpful_votes: 342,
    unhelpful_votes: 23,
    ...(overrides.review ?? {}),
  },
  product: {
    id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    canonical_name: "Anker Zolo Powerbank",
    source_url: "https://shopee.ph/x",
    platforms: [{ platform: "shopee", is_monetizable: true }],
    ...(overrides.product ?? {}),
  },
  author: {
    id: "99999999-8888-7777-6666-555555555555",
    display_name: "Viole-nim",
    trust_stage: 4,
    reputation_score: "99.00",
    ...(overrides.author === null ? {} : (overrides.author ?? {})),
  },
  suggested_platform: "shopee",
  suggested_sub_id: "blt_111111112222",
  signals: {
    velocity: false,
    collusion: false,
    duplicate_content: false,
    author_account_age_days: 730,
    author_review_count: 15,
    ...(overrides.signals ?? {}),
  },
  ...(overrides.author === null ? { author: null } : {}),
});

/** A report row as `GET /admin/reports` returns it. */
const report = (overrides = {}) => ({
  report: {
    id: "r1",
    log_id: "log-1",
    target_type: "review",
    target_ref: "11111111-2222-3333-4444-555555555555",
    reason: "spam",
    notes: null,
    evidence_url: null,
    created_at: "2026-09-07T12:00:00.000Z",
    ...(overrides.report ?? {}),
  },
  reporter: {
    id: "rep-1",
    display_name: "someone",
    username: "someone",
    trust_stage: 2,
  },
  target: {
    id: "11111111-2222-3333-4444-555555555555",
    title: "Solid Powerbank but gets warm",
    author_id: "99999999-8888-7777-6666-555555555555",
    is_published: false,
    ...(overrides.target ?? {}),
  },
  target_report_count: 3,
  ...(overrides.rest ?? {}),
});

/* ---------------------------------------------------------------- priority */

test("priorityOf is High when any advisory fraud signal fired", () => {
  assert.equal(priorityOf(item({ signals: { duplicate_content: true } })), "High");
  assert.equal(priorityOf(item({ signals: { collusion: true } })), "High");
  assert.equal(priorityOf(item({ signals: { velocity: true } })), "High");
});

test("priorityOf is High even when the proof of purchase is verified", () => {
  // Verification must not outrank a fired signal: a verified receipt on a
  // duplicated body is exactly the case a moderator must see first.
  const flagged = item({
    review: { verification_status: "verified" },
    signals: { collusion: true },
  });
  assert.equal(priorityOf(flagged), "High");
});

test("priorityOf is Normal when nothing fired but the receipt is unverified", () => {
  assert.equal(
    priorityOf(item({ review: { verification_status: "unverified" } })),
    "Normal",
  );
});

test("priorityOf is Low only when verified and no signal fired", () => {
  assert.equal(priorityOf(item()), "Low");
});

/* ------------------------------------------------------------- relative age */

test("relativeAge steps through each unit at its boundary", () => {
  const now = Date.parse("2026-09-08T12:00:00.000Z");
  const at = (ms) => relativeAge(new Date(now - ms).toISOString(), now);

  assert.equal(at(0), "0s ago");
  assert.equal(at(59_000), "59s ago");
  assert.equal(at(60_000), "1m ago");
  assert.equal(at(3_599_000), "59m ago");
  assert.equal(at(3_600_000), "1h ago");
  assert.equal(at(86_399_000), "23h ago");
  assert.equal(at(86_400_000), "1d ago");
  assert.equal(at(29 * 86_400_000), "29d ago");
  assert.equal(at(30 * 86_400_000), "1mo ago");
  assert.equal(at(364 * 86_400_000), "12mo ago");
  assert.equal(at(365 * 86_400_000), "1y ago");
});

test("relativeAge never renders a future timestamp as negative", () => {
  const now = Date.parse("2026-09-08T12:00:00.000Z");
  assert.equal(relativeAge("2026-09-08T12:00:30.000Z", now), "0s ago");
});

test("accountAgeLabel converts the queue's whole-day account age", () => {
  // `signals.author_account_age_days` is an integer day count, not a timestamp.
  assert.equal(accountAgeLabel(0), "0d ago");
  assert.equal(accountAgeLabel(29), "29d ago");
  assert.equal(accountAgeLabel(30), "1mo ago");
  assert.equal(accountAgeLabel(364), "12mo ago");
  assert.equal(accountAgeLabel(730), "2y ago");
});

/* --------------------------------------------------------------- queue rows */

test("queueRows matches the search against title, product and author", () => {
  // Every searchable field is distinct across rows, so a match can only come
  // from the field the assertion names.
  const rows = [
    item({
      review: { id: "a", title: "Solid Powerbank" },
      product: { canonical_name: "Alpha" },
      author: { display_name: "alice" },
    }),
    item({
      review: { id: "b", title: "Nothing alike" },
      product: { canonical_name: "Jisulife Fan" },
      author: { display_name: "bob" },
    }),
    item({
      review: { id: "c", title: "Nothing alike" },
      product: { canonical_name: "Gamma" },
      author: { display_name: "yuceann" },
    }),
    item({
      review: { id: "d", title: "Nothing alike" },
      product: { canonical_name: "Delta" },
      author: { display_name: "someone" },
    }),
  ];

  const byTitle = queueRows(rows, { query: "powerbank", priority: "", newestFirst: true });
  const byProduct = queueRows(rows, { query: "jisulife", priority: "", newestFirst: true });
  const byAuthor = queueRows(rows, { query: "YUCEANN", priority: "", newestFirst: true });

  assert.deepEqual(byTitle.map((r) => r.review.id), ["a"]);
  assert.deepEqual(byProduct.map((r) => r.review.id), ["b"]);
  assert.deepEqual(byAuthor.map((r) => r.review.id), ["c"]);
});

test("queueRows filters by derived priority", () => {
  const rows = [
    item({ review: { id: "high" }, signals: { velocity: true } }),
    item({ review: { id: "normal", verification_status: "unverified" } }),
    item({ review: { id: "low" } }),
  ];

  assert.deepEqual(
    queueRows(rows, { query: "", priority: "High", newestFirst: true }).map((r) => r.review.id),
    ["high"],
  );
  assert.deepEqual(
    queueRows(rows, { query: "", priority: "Normal", newestFirst: true }).map((r) => r.review.id),
    ["normal"],
  );
});

test("queueRows orders by created_at and reverses on demand", () => {
  const rows = [
    item({ review: { id: "old", created_at: "2026-01-01T00:00:00.000Z" } }),
    item({ review: { id: "new", created_at: "2026-09-01T00:00:00.000Z" } }),
    item({ review: { id: "mid", created_at: "2026-05-01T00:00:00.000Z" } }),
  ];

  assert.deepEqual(
    queueRows(rows, { query: "", priority: "", newestFirst: true }).map((r) => r.review.id),
    ["new", "mid", "old"],
  );
  assert.deepEqual(
    queueRows(rows, { query: "", priority: "", newestFirst: false }).map((r) => r.review.id),
    ["old", "mid", "new"],
  );
});

test("queueRows leaves the caller's array untouched", () => {
  // The screen holds `pending` as a prop; sorting it in place would reorder
  // React's own source of truth behind its back.
  const rows = [
    item({ review: { id: "old", created_at: "2026-01-01T00:00:00.000Z" } }),
    item({ review: { id: "new", created_at: "2026-09-01T00:00:00.000Z" } }),
  ];
  queueRows(rows, { query: "", priority: "", newestFirst: true });
  assert.deepEqual(rows.map((r) => r.review.id), ["old", "new"]);
});

/* ---------------------------------------------------------------- paginate */

test("paginate returns the page slice and a 1-based inclusive range", () => {
  const rows = Array.from({ length: 23 }, (_, i) => i);

  const second = paginate(rows, 10, 2);
  assert.deepEqual(second.visible, [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]);
  assert.equal(second.pageCount, 3);
  assert.equal(second.current, 2);
  assert.equal(second.firstIndex, 11);
  assert.equal(second.lastIndex, 20);

  const last = paginate(rows, 10, 3);
  assert.deepEqual(last.visible, [20, 21, 22]);
  assert.equal(last.firstIndex, 21);
  assert.equal(last.lastIndex, 23);
});

test("paginate clamps a page number past the end back onto the last page", () => {
  // Narrowing the filter while sitting on page 4 must not blank the table.
  const result = paginate(Array.from({ length: 5 }, (_, i) => i), 10, 4);
  assert.equal(result.current, 1);
  assert.deepEqual(result.visible, [0, 1, 2, 3, 4]);
});

test("paginate reports an empty range for no rows rather than 1-0", () => {
  const result = paginate([], 10, 1);
  assert.equal(result.pageCount, 1);
  assert.equal(result.firstIndex, 0);
  assert.equal(result.lastIndex, 0);
});

/* -------------------------------------------------------------- id + report */

test("reviewIdLabel prefers the backend's human reference", () => {
  assert.equal(
    reviewIdLabel({ review_id: "rev_a1b2c3d4e5", id: "11111111-2222-3333-4444-555555555555" }),
    "rev_a1b2c3d4e5",
  );
});

test("reviewIdLabel falls back to a short prefix of the UUID", () => {
  assert.equal(
    reviewIdLabel({ review_id: null, id: "11111111-2222-3333-4444-555555555555" }),
    "11111111",
  );
});

test("reportCountFor matches a report filed against the review's UUID", () => {
  assert.equal(reportCountFor(item(), [report()]), 3);
});

test("reportCountFor also matches a report filed against the human reference", () => {
  // `admin_overview_service` unions both forms when it counts reported
  // reviews; matching only the UUID would silently under-report.
  const byHumanRef = report({
    report: { target_ref: "rev_a1b2c3d4e5" },
    target: { id: "some-other-id" },
  });
  assert.equal(reportCountFor(item(), [byHumanRef]), 3);
});

test("reportCountFor is zero when no report targets this review", () => {
  const elsewhere = report({
    report: { target_ref: "rev_zzzzzzzzzz" },
    target: { id: "another-review" },
  });
  assert.equal(reportCountFor(item(), [elsewhere]), 0);
});

/* ------------------------------------------------------------- engagement */

test("engagementFor reports the review's real vote counts", () => {
  const stats = engagementFor(item(), [report()]);
  assert.equal(stats.upvotes, 342);
  assert.equal(stats.downvotes, 23);
});

test("engagementFor reports per-review reports from the loaded report feed", () => {
  const stats = engagementFor(item(), [report()]);
  assert.equal(stats.reports.available, true);
  assert.equal(stats.reports.value, "3");
});

test("engagementFor marks views, shares and comments unavailable rather than zero", () => {
  // Nothing in this build serves a per-review view, share or comment count to
  // the moderator console: `review_view_buckets` has no admin read path, no
  // share counter exists anywhere, and `comment_count` is only on
  // `GET /reviews/{id}/full`. Rendering "0" would state, on screen, that the
  // review has none — which is a different claim from "not measured here".
  const stats = engagementFor(item(), []);

  for (const key of ["views", "shares", "comments", "topComment"]) {
    assert.equal(stats[key].available, false, `${key} must not claim a number`);
    assert.ok(
      stats[key].reason.length > 0,
      `${key} must say why it is unavailable`,
    );
  }
});

test("engagementFor keeps views unavailable even for a fully populated card", () => {
  // Guards against a later change wiring Views to whichever number is nearest
  // to hand on the queue item.
  const stats = engagementFor(
    item({ review: { helpful_votes: 12900, unhelpful_votes: 17 } }),
    [report()],
  );
  assert.equal(stats.views.available, false);
  assert.equal(stats.shares.available, false);
});

/* --------------------------------------------------------- author trust card */

test("authorTrustStats reads age, trust score and review count from the queue card", () => {
  const stats = authorTrustStats(item());
  const byLabel = Object.fromEntries(stats.map((s) => [s.label, s]));

  assert.equal(byLabel["Age"].available, true);
  assert.equal(byLabel["Age"].value, "2y ago");
  assert.equal(byLabel["Trust Score"].available, true);
  assert.equal(byLabel["Trust Score"].value, "99");
  assert.equal(byLabel["Total Reviews"].available, true);
  assert.equal(byLabel["Total Reviews"].value, "15");
});

test("authorTrustStats marks Verified Reviews unavailable", () => {
  // `users.verified_review_count` exists but `QueueAuthor` does not carry it,
  // and `signals.author_review_count` counts ALL non-removed reviews — reusing
  // it here would overstate how much of this author's work was verified.
  const byLabel = Object.fromEntries(authorTrustStats(item()).map((s) => [s.label, s]));

  assert.equal(byLabel["Verified Reviews"].available, false);
  assert.ok(byLabel["Verified Reviews"].reason.length > 0);
  assert.notEqual(byLabel["Verified Reviews"].value, "15");
});

test("authorTrustStats never prints NaN for an unparseable trust score", () => {
  // reputation_score crosses the wire as a decimal string. If it ever arrives
  // empty or malformed, the cell must fall back to "not available" — printing
  // "NaN" beside a reviewer's name is worse than printing nothing.
  const byLabel = Object.fromEntries(
    authorTrustStats(item({ author: { reputation_score: "" } })).map((s) => [s.label, s]),
  );

  assert.equal(byLabel["Trust Score"].available, false);
  assert.notEqual(byLabel["Trust Score"].value, "NaN");
});

test("authorTrustStats survives a queue card whose author was deleted", () => {
  const stats = authorTrustStats(item({ author: null }));
  const byLabel = Object.fromEntries(stats.map((s) => [s.label, s]));

  assert.equal(byLabel["Trust Score"].available, false);
  // The signals block is author-independent, so it still resolves.
  assert.equal(byLabel["Total Reviews"].value, "15");
});
