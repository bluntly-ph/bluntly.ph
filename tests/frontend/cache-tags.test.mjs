import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { REVIEW_LISTS, isReportDecision, reviewTag, tagsToExpire } from "../../lib/cache-tags.ts";

/**
 * Which writes expire which cached review reads (2026-09-18: an upvote
 * committed, and every page kept showing the old count for a minute).
 */

const ID = "00000000-0000-0000-0000-0000000e0005";

test("a vote, unvote, comment, edit or report expires the review and the lists", () => {
  for (const [method, path] of [
    ["POST", `api/v1/reviews/${ID}/vote`],
    ["DELETE", `api/v1/reviews/${ID}/vote`],
    ["POST", `api/v1/reviews/${ID}/comments`],
    ["PATCH", `api/v1/reviews/${ID}`],
    ["POST", `api/v1/reviews/${ID}/report`],
  ]) {
    assert.deepEqual(tagsToExpire(method, path), [reviewTag(ID), REVIEW_LISTS], `${method} ${path}`);
  }
});

test("a moderator's publish, reject, unpublish or link expires the same", () => {
  for (const action of ["publish", "reject", "unpublish", "referral-link"]) {
    assert.deepEqual(tagsToExpire("POST", `api/v1/admin/reviews/${ID}/${action}`), [reviewTag(ID), REVIEW_LISTS]);
  }
});

test("a report decision expires the review it names, or the lists when it names none", () => {
  const path = `api/v1/admin/reports/${ID.replace("e0005", "f0001")}/decision`;
  assert.equal(isReportDecision(path), true);
  assert.deepEqual(tagsToExpire("POST", path, ID), [reviewTag(ID), REVIEW_LISTS]);
  assert.deepEqual(tagsToExpire("POST", path, null), [REVIEW_LISTS]);
});

test("reads, and writes to anything else, expire nothing", () => {
  assert.deepEqual(tagsToExpire("GET", `api/v1/reviews/${ID}/full`), []);
  assert.deepEqual(tagsToExpire("HEAD", `api/v1/reviews/${ID}`), []);
  assert.deepEqual(tagsToExpire("POST", "api/v1/reviews"), [], "a new review is pending, not public");
  assert.deepEqual(tagsToExpire("POST", "api/v1/requests/abc/upvote"), []);
  assert.deepEqual(tagsToExpire("POST", "api/v1/reviews/feed"), []);
  assert.deepEqual(tagsToExpire("POST", "api/v1/reviews/not-a-uuid/vote"), []);
});

test("the ids a write expires are the ids the reads were tagged with", () => {
  assert.deepEqual(tagsToExpire("POST", `api/v1/reviews/${ID.toUpperCase()}/vote`), [reviewTag(ID), REVIEW_LISTS]);
});

test("every public review read carries a tag, and the BFF expires them immediately", () => {
  const reviews = readFileSync(new URL("../../lib/reviews.ts", import.meta.url), "utf8");
  const cached = reviews.match(/revalidate: 60/g) ?? [];
  const tagged = reviews.match(/revalidate: 60,\s*tags: \[/g) ?? [];
  assert.ok(cached.length >= 5, "expected the public review reads in lib/reviews.ts");
  assert.equal(tagged.length, cached.length, "a cached review read in lib/reviews.ts has no tag");

  const bff = readFileSync(new URL("../../app/api/bff/[...path]/route.ts", import.meta.url), "utf8");
  assert.match(bff, /revalidateTag\(tag, \{ expire: 0 \}\)/);
  assert.doesNotMatch(bff, /revalidateTag\([^)]*"max"/, '"max" would serve the stale count once more');
});
