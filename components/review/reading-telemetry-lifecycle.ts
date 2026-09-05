import type { ReadingTelemetryPayload } from "@/lib/reading-telemetry";

/**
 * Pure decisions `ReadingTelemetry.tsx` makes about WHETHER to send, kept out
 * of that file so they can be unit-tested directly.
 *
 * `.ts`, not `.tsx`: Node's `--experimental-strip-types` (used by
 * `npm run test:frontend`) recognises `.ts`/`.mts` but has no handling for
 * `.tsx` at all — it is not a JSX question, the extension itself is simply
 * unregistered. `ReadingTelemetry.tsx` renders `null` and contains no JSX
 * either way, but that alone does not make the `.tsx` file importable from a
 * plain Node test; this sibling module is what actually is.
 */

//: Mirrors design §4.5's pinned MIN_ACTIVE_MS. `lib/reading-telemetry.ts`
//: keeps it private (Task 6's module boundary), so it is restated here rather
//: than exported speculatively for one caller.
export const MIN_ACTIVE_MS = 1_000;

//: Mirrors the pinned MAX_CHECKPOINTS (16, start included). `nextCheckpoint`
//: already enforces this for the periodic path; terminal and interaction
//: flushes do not go through `nextCheckpoint` at all, so they need the same
//: ceiling applied directly — the "one shared 16-write budget" this task's
//: binding update describes.
export const MAX_CHECKPOINTS = 16;

export function floorNow(raw: number): number {
  return Number.isFinite(raw) ? Math.floor(raw) : 0;
}

/**
 * True once every mutable field two payloads share is identical (`seq` is
 * excluded — it always differs). This is the terminal-flush dedup rule: a
 * pagehide with nothing new to report must not spend a write on a copy of the
 * last thing already sent.
 */
export function payloadsUnchanged(
  previous: ReadingTelemetryPayload | null,
  next: ReadingTelemetryPayload,
): boolean {
  if (!previous) return false;
  return (
    previous.active_ms === next.active_ms &&
    previous.body_active_ms === next.body_active_ms &&
    previous.wall_ms === next.wall_ms &&
    previous.scroll_pct === next.scroll_pct &&
    previous.vote_after_ms === next.vote_after_ms &&
    previous.report_after_ms === next.report_after_ms &&
    previous.comment_after_ms === next.comment_after_ms &&
    previous.share_after_ms === next.share_after_ms &&
    previous.photo_after_ms === next.photo_after_ms &&
    previous.outlink_after_ms === next.outlink_after_ms
  );
}

/**
 * The MIN_ACTIVE_MS floor (design §4.5): no checkpoint AFTER THE START is sent
 * below this much accumulated active time. The start checkpoint is exempt —
 * it always fires at active_ms = 0 by definition, which is the whole point of
 * it (§4.2). A checkpoint this floor blocks is not lost: `noteInteraction`
 * already recorded the value inside the accumulator, and it rides along on
 * whichever checkpoint eventually clears the floor.
 */
export function meetsPostStartFloor(activeMs: number): boolean {
  return activeMs >= MIN_ACTIVE_MS;
}

/**
 * The next fresh checkpoint attempt is allowed only under budget, past the
 * floor, and only if it says something the last send did not.
 */
export function shouldFlush(
  checkpointsSent: number,
  activeMs: number,
  candidate: ReadingTelemetryPayload,
  lastSent: ReadingTelemetryPayload | null,
): boolean {
  if (checkpointsSent >= MAX_CHECKPOINTS) return false;
  if (!meetsPostStartFloor(activeMs)) return false;
  return !payloadsUnchanged(lastSent, candidate);
}

/**
 * The body's read-through fraction: how far the viewport's bottom edge has
 * moved into the element, 0 at the top edge to 100 once the element's bottom
 * has scrolled past. Not specified by the design beyond "a percentage" — this
 * is the implementation's own choice of formula; the accumulator's own
 * `snapScroll` reduces it to one of the five legal milestones regardless of
 * the exact value, so precision here does not matter, only monotonic
 * direction under real scrolling.
 */
export function scrollProgress(rect: { top: number; height: number }, viewportHeight: number): number {
  if (rect.height <= 0) return 100;
  const read = viewportHeight - rect.top;
  return Math.max(0, Math.min(100, (read / rect.height) * 100));
}
