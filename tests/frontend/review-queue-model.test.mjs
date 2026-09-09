import assert from "node:assert/strict";
import test from "node:test";

import {
  accountAgeLabel,
  authorTrustStats,
  engagementFor,
  priorityOf,
  relativeAge,
  reportCountFor,
  reviewIdLabel,
  selectVisibleQueueItem,
  tabHref,
  VOTING_GEOGRAPHY_SHORT,
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
  priority: {
    policy_version: "review-priority-v1",
    lane: "routine",
    score: 0,
    band: "low",
    sla_state: "on_track",
    due_at: "2026-09-09T12:00:00.000Z",
    factors: [],
    ...(overrides.priority ?? {}),
  },
  queue_time_basis: overrides.queue_time_basis ?? "review_created_at",
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

test("priorityOf renders the band the server assessed", () => {
  assert.equal(priorityOf(item({ priority: { band: "high" } })), "High");
  assert.equal(priorityOf(item({ priority: { band: "normal" } })), "Normal");
  assert.equal(priorityOf(item()), "Low");
});

test("priorityOf does not consult the advisory signals", () => {
  // This is the behaviour change. The signals below all fired, and under the
  // old local rule that alone made the row High; the policy weighed them
  // against everything else and returned Low. The console reports the policy.
  const flagged = item({
    signals: { velocity: true, collusion: true, duplicate_content: true },
    priority: { band: "low" },
  });
  assert.equal(priorityOf(flagged), "Low");
});

test("priorityOf does not consult verification status", () => {
  const unverified = item({
    review: { verification_status: "unverified" },
    priority: { band: "low" },
  });
  assert.equal(priorityOf(unverified), "Low");
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

/* ------------------------------------------ ordering, filtering, paging */

/*
 * The `queueRows` and `paginate` suites were removed with the functions they
 * covered. They asserted that the browser could search, filter by a locally
 * derived band, re-sort by date and cut its own page — four whole-queue claims
 * made from one page of rows. The server does all of it now, over the whole
 * backlog, before the page exists. `moderation-priority-contract.test.mjs`
 * covers what replaced them: the URL filters, and the absence of these two.
 */

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

test("reportCountFor is unavailable when the partial feed has no matching target", () => {
  const elsewhere = report({
    report: { target_ref: "rev_zzzzzzzzzz" },
    target: { id: "another-review" },
  });
  assert.equal(reportCountFor(item(), [elsewhere]), null);
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

test("engagementFor never turns absence from a partial report feed into zero", () => {
  const stats = engagementFor(item(), []);
  assert.equal(stats.reports.available, false);
  assert.match(stats.reports.reason, /partial|available/i);
});

test("selectVisibleQueueItem cannot retain a detail outside the visible page", () => {
  const first = item({ review: { id: "first" } });
  const second = item({ review: { id: "second" } });
  assert.equal(selectVisibleQueueItem([first], "second")?.review.id, "first");
  assert.equal(selectVisibleQueueItem([], "second"), null);
  // The same id IS honoured once that row is on the visible page, which is
  // what makes the fallback above a filter/paging rule rather than the
  // selection being ignored outright.
  assert.equal(selectVisibleQueueItem([first, second], "second")?.review.id, "second");
});

const noFilters = {
  band: "", lane: "", sla: "", factor: "", q: "", limit: 50, offset: 0,
};

test("tabHref makes the URL the shareable source of truth", () => {
  assert.equal(
    tabHref("answers", { ...noFilters, band: "high" }),
    "/moderate/review-queue?tab=answers&band=high",
  );
  assert.equal(tabHref("reviews", noFilters), "/moderate/review-queue?tab=reviews");
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

test("the geography label does not claim vote geography goes unrecorded", () => {
  // `review_first_vote_geo_buckets` DOES store per-review vote geography — it
  // is written on every first vote. What is missing is a read path. Saying it
  // is "not measured" tells a moderator the opposite of the truth, and would
  // send anyone chasing a retention or privacy question to the wrong place.
  assert.doesNotMatch(VOTING_GEOGRAPHY_SHORT, /not (measured|collected|recorded|tracked)/i);
  assert.match(VOTING_GEOGRAPHY_SHORT, /collected|recorded|stored/i);
});
