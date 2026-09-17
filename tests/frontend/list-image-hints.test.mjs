import assert from "node:assert/strict";
import test from "node:test";

import { LAZY, firstImageIndex, listImageHints } from "../../lib/list-image-hints.ts";

/**
 * Which list thumbnails load eagerly, and which one gets high fetch priority.
 * Production /search named a LAZY image as its LCP element because row 0 had no
 * photo and `priority` was pinned to row 0.
 */

const rows = [{ imageUrl: null }, { imageUrl: null }, { imageUrl: "a.png" }, { imageUrl: "b.png" }, { imageUrl: "c.png" }];
const first = firstImageIndex(rows, (r) => Boolean(r.imageUrl));

test("the first row WITH an image is found, not row 0", () => {
  assert.equal(first, 2);
});

test("that row is eager and high priority when it is above the fold", () => {
  assert.deepEqual(listImageHints(2, first, 4), { loading: "eager", fetchPriority: "high" });
});

test("other visible rows are eager but not high priority", () => {
  assert.deepEqual(listImageHints(3, first, 4), { loading: "eager", fetchPriority: "auto" });
});

test("rows below the fold stay lazy", () => {
  assert.deepEqual(listImageHints(4, first, 4), LAZY);
});

test("a first image below the fold gets no high priority — it cannot be the LCP", () => {
  assert.deepEqual(listImageHints(2, first, 2), LAZY);
});

test("a list with no images asks for nothing high", () => {
  const none = firstImageIndex([{ imageUrl: null }], (r) => Boolean(r.imageUrl));
  assert.equal(none, -1);
  assert.equal(listImageHints(0, none, 4).fetchPriority, "auto");
});
