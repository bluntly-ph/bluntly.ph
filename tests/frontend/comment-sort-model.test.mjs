import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_COMMENT_SORT,
  helpfulnessOf,
  sortComments,
} from "../../components/review/comment-sort-model.ts";

const c = (id, helpful, unhelpful, iso) => ({
  id,
  helpful_votes: helpful,
  unhelpful_votes: unhelpful,
  created_at: iso,
});

const ids = (list) => list.map((x) => x.id);

// Deliberately out of order on both axes.
const THREAD = [
  c("old-weak", 1, 0, "2026-01-01T00:00:00Z"),
  c("new-strong", 9, 1, "2026-03-01T00:00:00Z"),
  c("old-strong", 8, 0, "2026-01-15T00:00:00Z"),
  c("new-weak", 2, 1, "2026-04-01T00:00:00Z"),
];

test("helpfulness is net, not raw upvotes", () => {
  // 9 up / 8 down is not more helpful than 3 up / 0 down.
  assert.equal(helpfulnessOf(c("a", 9, 8, "2026-01-01T00:00:00Z")), 1);
  assert.equal(helpfulnessOf(c("b", 3, 0, "2026-01-01T00:00:00Z")), 3);
});

test("most helpful first is the default", () => {
  assert.deepEqual(DEFAULT_COMMENT_SORT, { rating: "most_helpful", date: "latest" });
  // net: old-strong 8, new-strong 8, new-weak 1, old-weak 1
  assert.deepEqual(ids(sortComments(THREAD)), [
    "new-strong",
    "old-strong",
    "new-weak",
    "old-weak",
  ]);
});

test("least helpful first reverses the rating axis", () => {
  assert.deepEqual(
    ids(sortComments(THREAD, { rating: "least_helpful", date: "latest" })),
    ["new-weak", "old-weak", "new-strong", "old-strong"],
  );
});

test("date breaks ties within an equal helpfulness", () => {
  // old-strong and new-strong are both net 8; the date axis decides.
  const latest = ids(sortComments(THREAD, { rating: "most_helpful", date: "latest" }));
  const oldest = ids(sortComments(THREAD, { rating: "most_helpful", date: "oldest" }));

  assert.deepEqual(latest.slice(0, 2), ["new-strong", "old-strong"]);
  assert.deepEqual(oldest.slice(0, 2), ["old-strong", "new-strong"]);
});

test("rating outranks date — the date axis never reorders unequal comments", () => {
  const oldest = sortComments(THREAD, { rating: "most_helpful", date: "oldest" });
  const net = oldest.map(helpfulnessOf);

  assert.deepEqual(net, [...net].sort((a, b) => b - a), "still descending by helpfulness");
});

test("the input array is never mutated", () => {
  const before = ids(THREAD);
  sortComments(THREAD, { rating: "least_helpful", date: "oldest" });

  assert.deepEqual(ids(THREAD), before, "React state must not be sorted in place");
});

test("an unparseable date does not throw or jump to an end", () => {
  const messy = [
    c("bad", 5, 0, "not-a-date"),
    c("good", 5, 0, "2026-01-01T00:00:00Z"),
  ];

  const out = sortComments(messy);
  assert.equal(out.length, 2);
  assert.deepEqual(ids(out).sort(), ["bad", "good"]);
});

test("missing vote counts are treated as zero", () => {
  const sparse = [
    { id: "none", created_at: "2026-01-01T00:00:00Z" },
    c("some", 2, 0, "2026-01-01T00:00:00Z"),
  ];

  assert.deepEqual(ids(sortComments(sparse)), ["some", "none"]);
});

test("an empty thread sorts to an empty thread", () => {
  assert.deepEqual(sortComments([]), []);
});
