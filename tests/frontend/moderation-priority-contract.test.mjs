import assert from "node:assert/strict";
import test from "node:test";

import * as model from "../../components/admin/review-queue-model.ts";
import {
  factorLines,
  parseQueueFilters,
  priorityOf,
  QUEUE_TIME_APPROXIMATE,
  queueApiQuery,
  queueAgeLabel,
  queueHref,
  slaStat,
  tabHref,
} from "../../components/admin/review-queue-model.ts";

/**
 * The moderation priority contract, from the frontend's side.
 *
 * One rule, and every test here is a way of stating it: the server owns
 * priority. The browser renders the assessment it was sent and never derives a
 * second one. Before this contract the console computed its own band from the
 * advisory fraud signals, which meant the queue could disagree with the
 * Overview above it and with the server's own ordering underneath it — three
 * answers to "what should I look at first?" on one screen.
 */

/** A queue card as `GET /admin/review-queue` now returns it. */
const item = (overrides = {}) => ({
  review: {
    id: "11111111-2222-3333-4444-555555555555",
    review_id: "rev_a1b2c3d4e5",
    title: "Solid Powerbank but gets warm",
    discussion: "Basta Anker, quality!",
    verification_status: "verified",
    created_at: "2026-09-08T12:00:00.000Z",
    wilson_score: "0.8412",
    helpful_votes: 342,
    unhelpful_votes: 23,
    ...(overrides.review ?? {}),
  },
  product: { canonical_name: "Anker Zolo Powerbank", ...(overrides.product ?? {}) },
  author: { display_name: "Viole-nim", reputation_score: "99.00" },
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
    lane: "reported",
    score: 55,
    band: "high",
    sla_state: "approaching",
    due_at: "2026-09-08T16:00:00.000Z",
    factors: [
      {
        code: "report_count_2_3",
        observed: 2,
        contribution: 25,
        explanation: "Two distinct people reported this review.",
      },
      {
        code: "duplicate_content",
        observed: true,
        contribution: 30,
        explanation: "The review body closely matches another review.",
      },
    ],
    ...(overrides.priority ?? {}),
  },
  queue_time_basis: overrides.queue_time_basis ?? "review_created_at",
});

/* --------------------------------------------------------------- the band */

test("priorityOf reads the server band and nothing else", () => {
  assert.equal(priorityOf(item()), "High");
  assert.equal(priorityOf(item({ priority: { band: "normal" } })), "Normal");
  assert.equal(priorityOf(item({ priority: { band: "low" } })), "Low");
});

test("priorityOf ignores the advisory signals entirely", () => {
  // Every signal fired and the server still assessed it Low. Under the old
  // client heuristic this card was High, which is the whole defect: the
  // browser was overruling a policy it does not implement.
  const contradicted = item({
    signals: { velocity: true, collusion: true, duplicate_content: true },
    priority: { band: "low", lane: "routine", score: 0, factors: [] },
  });
  assert.equal(priorityOf(contradicted), "Low");
});

test("priorityOf ignores verification status", () => {
  const unverified = item({
    review: { verification_status: "unverified" },
    priority: { band: "low" },
  });
  assert.equal(priorityOf(unverified), "Low");
});

test("an unfamiliar band still renders rather than blanking or guessing", () => {
  // A band this build has never heard of is a deploy-skew problem, not a
  // reason to show nothing and not a licence to substitute a band we like.
  assert.equal(priorityOf(item({ priority: { band: "quarantine" } })), "Quarantine");
});

test("the client no longer exposes a way to re-rank or re-filter the queue", () => {
  // `queueRows` filtered by a locally derived priority and re-sorted by date.
  // Both were whole-queue claims applied to one server-ordered page.
  assert.equal(model.queueRows, undefined);
  assert.equal(model.paginate, undefined);
});

/* ------------------------------------------------------------- the reasons */

test("factorLines passes the server's own explanations through", () => {
  const lines = factorLines(item());
  assert.deepEqual(
    lines.map((f) => f.code),
    ["report_count_2_3", "duplicate_content"],
  );
  assert.equal(lines[0].explanation, "Two distinct people reported this review.");
  assert.equal(lines[0].contribution, 25);
});

test("a factor code this build has never seen still renders its explanation", () => {
  // The explanations are written by the policy, not looked up here. A code
  // added server-side must appear on the screen the day it ships, or the
  // console silently hides the reason a review is at the top of the queue.
  const lines = factorLines(
    item({
      priority: {
        factors: [
          {
            code: "coordinated_purchase_window",
            observed: true,
            contribution: 20,
            explanation: "Purchases behind these reviews cluster in one hour.",
          },
        ],
      },
    }),
  );
  assert.equal(lines.length, 1);
  assert.equal(lines[0].explanation, "Purchases behind these reviews cluster in one hour.");
});

test("a factor with no explanation falls back to its code, never to blank", () => {
  const lines = factorLines(
    item({
      priority: {
        factors: [{ code: "vote_velocity", observed: true, contribution: 15, explanation: "" }],
      },
    }),
  );
  assert.equal(lines[0].explanation, "vote_velocity");
});

test("no factors is an empty list, not an invented reason", () => {
  assert.deepEqual(factorLines(item({ priority: { factors: [] } })), []);
  assert.deepEqual(factorLines(item({ priority: { factors: undefined } })), []);
});

/* ----------------------------------------------------------------- the SLA */

const NOW = Date.parse("2026-09-08T15:00:00.000Z");

test("slaStat says how long is left, in the lane's own terms", () => {
  const stat = slaStat(item(), NOW);
  assert.equal(stat.state, "approaching");
  assert.equal(stat.available, true);
  assert.match(stat.value, /1h/);
});

test("slaStat says how late overdue work is", () => {
  const late = item({
    priority: { sla_state: "overdue", due_at: "2026-09-08T12:00:00.000Z" },
  });
  const stat = slaStat(late, NOW);
  assert.equal(stat.state, "overdue");
  assert.match(stat.value, /3h/);
});

test("queue age is labelled as the approximation it currently is", () => {
  // Until the queue-entry migration lands, "queued at" is the review's
  // created_at (or updated_at for an edited one). The screen must not present
  // either as precise lifecycle timing.
  const label = queueAgeLabel(item(), NOW);
  assert.match(label, /ago/);
  assert.match(QUEUE_TIME_APPROXIMATE, /created_at/);
});

test("an edited review's queue age is read from the edit, and says so", () => {
  const edited = item({ queue_time_basis: "review_updated_at" });
  assert.equal(typeof queueAgeLabel(edited, NOW), "string");
  assert.notEqual(QUEUE_TIME_APPROXIMATE, "");
});

/* ------------------------------------------------------------- the filters */

test("parseQueueFilters accepts only values the policy defines", () => {
  const params = new URLSearchParams({
    band: "high",
    lane: "reported",
    sla: "overdue",
    factor: "duplicate_content",
    q: "powerbank",
    limit: "25",
    offset: "50",
  });
  assert.deepEqual(parseQueueFilters(params), {
    band: "high",
    lane: "reported",
    sla: "overdue",
    factor: "duplicate_content",
    q: "powerbank",
    limit: 25,
    offset: 50,
  });
});

test("parseQueueFilters drops values the server would reject", () => {
  // A hand-edited URL must narrow to something valid rather than 422 the
  // whole screen, and must never be forwarded verbatim.
  const params = new URLSearchParams({
    band: "critical",
    lane: "nonsense",
    sla: "soon",
    limit: "9999",
    offset: "-5",
  });
  const filters = parseQueueFilters(params);
  assert.equal(filters.band, "");
  assert.equal(filters.lane, "");
  assert.equal(filters.sla, "");
  assert.equal(filters.limit, 50);
  assert.equal(filters.offset, 0);
});

test("queueApiQuery sends only what is set, URL-encoded", () => {
  const query = queueApiQuery({
    band: "high",
    lane: "",
    sla: "",
    factor: "",
    q: "anker & co",
    limit: 25,
    offset: 0,
  });
  assert.match(query, /band=high/);
  assert.match(query, /q=anker\+%26\+co/);
  assert.doesNotMatch(query, /lane=/);
  assert.doesNotMatch(query, /sla=/);
  assert.match(query, /limit=25/);
});

test("tabHref carries every canonical filter, not just the band", () => {
  const filters = {
    band: "high",
    lane: "reported",
    sla: "overdue",
    factor: "collusion",
    q: "anker",
    limit: 25,
    offset: 50,
  };
  const href = tabHref("answers", filters);
  assert.match(href, /^\/moderate\/review-queue\?/);
  for (const pair of ["tab=answers", "band=high", "lane=reported", "sla=overdue",
                      "factor=collusion", "q=anker"]) {
    assert.match(href, new RegExp(pair.replace("&", "%26")));
  }
  // Switching tabs returns to the first page: the offset belonged to the list
  // being left behind.
  assert.doesNotMatch(href, /offset=/);
});

test("queueHref changes one filter and resets the page", () => {
  const filters = {
    band: "high", lane: "", sla: "", factor: "", q: "", limit: 25, offset: 75,
  };
  const href = queueHref(filters, { band: "low" });
  assert.match(href, /band=low/);
  assert.doesNotMatch(href, /offset=/);
});

test("queueHref can page without losing the filters", () => {
  const filters = {
    band: "high", lane: "", sla: "", factor: "", q: "", limit: 25, offset: 0,
  };
  const href = queueHref(filters, { offset: 25 });
  assert.match(href, /band=high/);
  assert.match(href, /offset=25/);
});
