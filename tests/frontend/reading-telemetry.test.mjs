import assert from "node:assert/strict";
import test from "node:test";

import {
  ReadingAccumulator,
  nextCheckpoint,
  snapScroll,
} from "../../lib/reading-telemetry.ts";
import {
  meetsPostStartFloor,
  payloadsUnchanged,
  shouldFlush,
} from "../../components/review/reading-telemetry-lifecycle.ts";

const allGates = {
  visible: true,
  focused: true,
  recentlyActive: true,
  bodyVisible: true,
};

test("accumulates wall time while all three active page gates and the body gate hold", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_200, allGates);

  assert.deepEqual(accumulator.payload("impression-a", "review-a", 0), {
    impression_id: "impression-a",
    review_id: "review-a",
    seq: 0,
    active_ms: 1_200,
    body_active_ms: 1_200,
    wall_ms: 1_200,
    scroll_pct: 0,
    vote_after_ms: null,
    report_after_ms: null,
    comment_after_ms: null,
    share_after_ms: null,
    photo_after_ms: null,
    outlink_after_ms: null,
  });
});

test("requires every active page gate while wall time continues", () => {
  for (const gates of [
    { ...allGates, visible: false },
    { ...allGates, focused: false },
    { ...allGates, recentlyActive: false },
  ]) {
    const accumulator = new ReadingAccumulator(0);
    accumulator.advance(800, gates);
    const payload = accumulator.payload("impression-a", "review-a", 1);

    assert.equal(payload.wall_ms, 800);
    assert.equal(payload.active_ms, 0);
    assert.equal(payload.body_active_ms, 0);
  }
});

test("requires body visibility for body-active time but not active time", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_500, { ...allGates, bodyVisible: false });

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 1_500);
  assert.equal(payload.active_ms, 1_500);
  assert.equal(payload.body_active_ms, 0);
});

test("does not backfill an idle gap after noteActivity resumes reading", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(30_001, { ...allGates, recentlyActive: false });
  accumulator.noteActivity(45_000, allGates);
  accumulator.advance(46_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 46_000);
  assert.equal(payload.active_ms, 1_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("keeps valid active time when fresh activity occurs between eligible ticks", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(1_500, allGates);
  accumulator.advance(2_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 2_000);
  assert.equal(payload.body_active_ms, 2_000);
});

test("keeps the eligible prefix when an advance crosses the thirty-second freshness boundary", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(29_000, allGates);
  accumulator.advance(31_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 30_000);
  assert.equal(payload.body_active_ms, 30_000);
});

test("keeps the prior freshness prefix when delayed activity resumes reading", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(29_000, allGates);
  accumulator.noteActivity(45_000, allGates);
  accumulator.advance(46_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 31_000);
  assert.equal(payload.body_active_ms, 31_000);
  assert.equal(payload.wall_ms, 46_000);
});

test("does not invent or regress time for initial and backwards activity timestamps", () => {
  const initial = new ReadingAccumulator(0);
  initial.noteActivity(5_000, allGates);
  assert.equal(initial.payload("impression-a", "review-a", 0).active_ms, 0);
  assert.equal(initial.payload("impression-a", "review-a", 0).wall_ms, 0);

  const accumulator = new ReadingAccumulator(0);
  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(500, allGates);
  accumulator.advance(2_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 2_000);
  assert.equal(payload.body_active_ms, 2_000);
  assert.equal(payload.wall_ms, 2_000);
});

test("uses current gates when activity follows a focus false-to-true transition", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, { ...allGates, focused: false });
  accumulator.noteActivity(1_500, allGates);
  accumulator.advance(2_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 2_000);
  assert.equal(payload.active_ms, 1_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("uses current gates when activity follows a focus true-to-false transition", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(1_500, { ...allGates, focused: false });
  accumulator.advance(2_000, { ...allGates, focused: false });

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 2_000);
  assert.equal(payload.active_ms, 1_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("uses current gates when activity follows a body hidden-to-visible transition", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, { ...allGates, bodyVisible: false });
  accumulator.noteActivity(1_500, allGates);
  accumulator.advance(2_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 2_000);
  assert.equal(payload.active_ms, 2_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("uses current gates when activity follows a visible-to-hidden transition", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(1_500, { ...allGates, visible: false });
  accumulator.advance(2_000, { ...allGates, visible: false });

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 2_000);
  assert.equal(payload.active_ms, 1_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("ignores omitted or malformed activity gates without inventing time", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(29_000, allGates);
  assert.doesNotThrow(() => accumulator.noteActivity(45_000));
  assert.doesNotThrow(() => accumulator.noteActivity(45_000, { ...allGates, focused: "yes" }));
  accumulator.advance(46_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 46_000);
  assert.equal(payload.active_ms, 30_000);
  assert.equal(payload.body_active_ms, 30_000);
});

test("requires callers to advance with prior gates before a gate transition", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, allGates);
  accumulator.advance(2_000, { ...allGates, visible: false, bodyVisible: false });
  accumulator.advance(3_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 3_000);
  assert.equal(payload.active_ms, 2_000);
  assert.equal(payload.body_active_ms, 2_000);
});

test("ignores backwards clocks and caps every cumulative duration at thirty minutes", () => {
  const accumulator = new ReadingAccumulator(10_000);

  accumulator.advance(9_000, allGates);
  for (let elapsed = 30_000; elapsed <= 1_800_000; elapsed += 30_000) {
    accumulator.noteActivity(10_000 + elapsed - 30_000, allGates);
    accumulator.advance(10_000 + elapsed, allGates);
  }
  accumulator.advance(1_810_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 1_800_000);
  assert.equal(payload.active_ms, 1_800_000);
  assert.equal(payload.body_active_ms, 1_800_000);
});

test("snaps scroll downward and preserves the greatest coarse milestone", () => {
  assert.equal(snapScroll(-1), 0);
  assert.equal(snapScroll(24.9), 0);
  assert.equal(snapScroll(25), 25);
  assert.equal(snapScroll(74.99), 50);
  assert.equal(snapScroll(1000), 100);

  const accumulator = new ReadingAccumulator(0);
  accumulator.noteScroll(74);
  accumulator.noteScroll(30);
  accumulator.noteScroll(88);

  assert.equal(accumulator.payload("impression-a", "review-a", 1).scroll_pct, 75);
});

test("returns each checkpoint threshold once and stops after start plus fifteen follow-ups", () => {
  const sent = new Set([0]);
  const thresholds = [];
  let checkpointsSent = 1;

  for (;;) {
    const threshold = nextCheckpoint(1_800_000, sent, checkpointsSent);
    if (threshold === null) break;
    thresholds.push(threshold);
    sent.add(threshold);
    checkpointsSent += 1;
  }

  assert.deepEqual(thresholds, [
    10_000,
    30_000,
    60_000,
    120_000,
    240_000,
    360_000,
    480_000,
    600_000,
    720_000,
    840_000,
    960_000,
    1_080_000,
    1_200_000,
    1_320_000,
    1_440_000,
  ]);
  assert.equal(sent.size, 16);
  assert.equal(nextCheckpoint(1_800_000, sent, checkpointsSent), null);
  assert.equal(nextCheckpoint(9_999, new Set([0]), 1), null);
});

test("honors the total checkpoint budget when interaction and terminal writes use its remaining slots", () => {
  const periodicThresholds = new Set([0, 10_000, 30_000, 60_000]);

  assert.equal(nextCheckpoint(1_800_000, periodicThresholds, 15), 120_000);
  assert.equal(nextCheckpoint(1_800_000, periodicThresholds, 16), null);
});

test("fails closed unless the total checkpoint count is a nonnegative integer below sixteen", () => {
  const sent = new Set([0]);

  for (const count of [undefined, Number.NaN, Infinity, 15.5, -1, 16]) {
    assert.equal(nextCheckpoint(10_000, sent, count), null);
  }
});

test("payload contains exactly the thirteen client fields with cumulative values", () => {
  const accumulator = new ReadingAccumulator(0);
  accumulator.advance(1_250, allGates);
  accumulator.noteScroll(55);

  const start = accumulator.payload("impression-a", "review-a", 0);
  accumulator.advance(2_000, allGates);
  const later = accumulator.payload("impression-a", "review-a", 1);

  assert.deepEqual(Object.keys(later).sort(), [
    "active_ms",
    "body_active_ms",
    "comment_after_ms",
    "impression_id",
    "outlink_after_ms",
    "photo_after_ms",
    "report_after_ms",
    "review_id",
    "scroll_pct",
    "seq",
    "share_after_ms",
    "vote_after_ms",
    "wall_ms",
  ]);
  assert.equal(Object.keys(later).length, 13);
  assert.equal(start.seq, 0);
  assert.equal(later.seq, 1);
  assert.equal(later.wall_ms, 2_000);
  assert.equal(later.active_ms, 2_000);
  assert.equal(later.body_active_ms, 2_000);
  assert.equal(later.scroll_pct, 50);
});

test("keeps only each interaction kind's first relative occurrence within the session cap", () => {
  const accumulator = new ReadingAccumulator(10_000);

  accumulator.noteInteraction("vote", 10_900);
  accumulator.noteInteraction("vote", 12_000);
  accumulator.noteInteraction("report", 1_900_000);
  accumulator.noteInteraction("comment", 9_000);
  accumulator.noteInteraction("share", 40_000);
  accumulator.noteInteraction("photo", 50_000);
  accumulator.noteInteraction("outlink", 60_000);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.vote_after_ms, 900);
  assert.equal(payload.report_after_ms, 1_800_000);
  assert.equal(payload.comment_after_ms, 0);
  assert.equal(payload.share_after_ms, 30_000);
  assert.equal(payload.photo_after_ms, 40_000);
  assert.equal(payload.outlink_after_ms, 50_000);
});

// --- Task 7: the lifecycle component's own pure decisions -------------------
//
// ReadingTelemetry.tsx renders `null` and contains no JSX, so it is plain
// TypeScript end to end and importable here exactly like lib/reading-telemetry
// — these two functions are the only logic in that file worth testing outside
// a browser; everything else is `document`/`window`/`IntersectionObserver`
// wiring, which is what e2e/reading-telemetry.spec.ts exists to prove.

function payload(overrides = {}) {
  return {
    impression_id: "impression-a",
    review_id: "review-a",
    seq: 0,
    active_ms: 0,
    body_active_ms: 0,
    wall_ms: 0,
    scroll_pct: 0,
    vote_after_ms: null,
    report_after_ms: null,
    comment_after_ms: null,
    share_after_ms: null,
    photo_after_ms: null,
    outlink_after_ms: null,
    ...overrides,
  };
}

test("payloadsUnchanged treats a first send as always changed", () => {
  assert.equal(payloadsUnchanged(null, payload()), false);
});

test("payloadsUnchanged ignores seq and compares every other field", () => {
  const previous = payload({ seq: 3, active_ms: 5_000 });
  const next = payload({ seq: 4, active_ms: 5_000 });
  assert.equal(payloadsUnchanged(previous, next), true);
});

test("payloadsUnchanged detects a change in any single mutable field", () => {
  const previous = payload({ active_ms: 5_000 });
  for (const [field, value] of [
    ["active_ms", 5_001],
    ["body_active_ms", 1],
    ["wall_ms", 1],
    ["scroll_pct", 25],
    ["vote_after_ms", 100],
    ["report_after_ms", 100],
    ["comment_after_ms", 100],
    ["share_after_ms", 100],
    ["photo_after_ms", 100],
    ["outlink_after_ms", 100],
  ]) {
    const next = payload({ active_ms: 5_000, [field]: value });
    assert.equal(
      payloadsUnchanged(previous, next),
      false,
      `expected a change in ${field} to be detected`,
    );
  }
});

test("meetsPostStartFloor enforces the pinned MIN_ACTIVE_MS = 1000 threshold", () => {
  assert.equal(meetsPostStartFloor(0), false);
  assert.equal(meetsPostStartFloor(999), false);
  assert.equal(meetsPostStartFloor(1_000), true);
  assert.equal(meetsPostStartFloor(1_800_000), true);
});

test("shouldFlush refuses once the total checkpoint budget is spent", () => {
  const candidate = payload({ active_ms: 5_000 });
  assert.equal(shouldFlush(16, 5_000, candidate, null), false);
  assert.equal(shouldFlush(15, 5_000, candidate, null), true);
});

test("shouldFlush refuses below the MIN_ACTIVE_MS floor even with budget and a change", () => {
  const candidate = payload({ active_ms: 999, scroll_pct: 25 });
  assert.equal(shouldFlush(1, 999, candidate, payload()), false);
});

test("shouldFlush refuses an unchanged candidate and allows a changed one", () => {
  const previous = payload({ active_ms: 5_000 });
  assert.equal(shouldFlush(1, 5_000, payload({ active_ms: 5_000 }), previous), false);
  assert.equal(shouldFlush(1, 5_000, payload({ active_ms: 5_001 }), previous), true);
});
