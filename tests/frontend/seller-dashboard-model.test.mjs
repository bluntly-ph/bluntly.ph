import assert from "node:assert/strict";
import test from "node:test";

import { monthLabel, volumeBars } from "../../components/sellers/seller-model.ts";

/**
 * The owner dashboard's review-volume bars. The API sends every month in the
 * window, zero-filled, so a quiet month is drawn as an empty bar rather than
 * skipped — which is what would let a chart imply steady volume.
 */

test("a month is labelled in words, independent of the browser's locale", () => {
  assert.equal(monthLabel("2026-09"), "Sep 2026");
  assert.equal(monthLabel("2025-12"), "Dec 2025");
  assert.equal(monthLabel("not-a-month"), "not-a-month");
});

test("each bar is a share of the busiest month, in the order given", () => {
  const bars = volumeBars([
    { month: "2026-07", count: 2 },
    { month: "2026-08", count: 0 },
    { month: "2026-09", count: 4 },
  ]);
  assert.deepEqual(bars.map((b) => b.month), ["2026-07", "2026-08", "2026-09"]);
  assert.deepEqual(bars.map((b) => b.share), [0.5, 0, 1]);
});

test("a window with no reviews draws empty bars, not a division by zero", () => {
  const bars = volumeBars([{ month: "2026-08", count: 0 }, { month: "2026-09", count: 0 }]);
  assert.ok(bars.every((b) => b.share === 0));
});
