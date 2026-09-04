import assert from "node:assert/strict";
import test from "node:test";

import {
  ReadingAccumulator,
  nextCheckpoint,
  snapScroll,
} from "../../lib/reading-telemetry.ts";

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
  accumulator.noteActivity(45_000);
  accumulator.advance(46_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.wall_ms, 46_000);
  assert.equal(payload.active_ms, 1_000);
  assert.equal(payload.body_active_ms, 1_000);
});

test("keeps valid active time when fresh activity occurs between eligible ticks", () => {
  const accumulator = new ReadingAccumulator(0);

  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(1_500);
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
  accumulator.noteActivity(45_000);
  accumulator.advance(46_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 31_000);
  assert.equal(payload.body_active_ms, 31_000);
  assert.equal(payload.wall_ms, 46_000);
});

test("does not invent or regress time for initial and backwards activity timestamps", () => {
  const initial = new ReadingAccumulator(0);
  initial.noteActivity(5_000);
  assert.equal(initial.payload("impression-a", "review-a", 0).active_ms, 0);
  assert.equal(initial.payload("impression-a", "review-a", 0).wall_ms, 0);

  const accumulator = new ReadingAccumulator(0);
  accumulator.advance(1_000, allGates);
  accumulator.noteActivity(500);
  accumulator.advance(2_000, allGates);

  const payload = accumulator.payload("impression-a", "review-a", 1);
  assert.equal(payload.active_ms, 2_000);
  assert.equal(payload.body_active_ms, 2_000);
  assert.equal(payload.wall_ms, 2_000);
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
    accumulator.noteActivity(10_000 + elapsed - 30_000);
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
