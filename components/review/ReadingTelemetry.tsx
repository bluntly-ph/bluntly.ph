"use client";

import { useEffect } from "react";

import {
  MAX_SESSION_MS,
  ReadingAccumulator,
  nextCheckpoint,
  type ActivityGates,
  type ReadingTelemetryPayload,
} from "@/lib/reading-telemetry";
import {
  TELEMETRY_EVENT,
  type InteractionDetail,
  type InteractionKind,
} from "@/lib/reading-telemetry-events";

import { floorNow, scrollProgress, shouldFlush } from "./reading-telemetry-lifecycle";

/**
 * Mounts the review-page reading lifecycle: one impression, one accumulator,
 * sparse writes. Renders nothing and holds no React state — every mutable
 * value here is a closure variable local to one effect run, so a bug in this
 * module can corrupt a beacon body but can never throw into the page around
 * it or force an extra render.
 *
 * The decision logic (what counts as "changed", the MIN_ACTIVE_MS floor, the
 * 16-write budget) lives in `./reading-telemetry-lifecycle.ts`, a plain `.ts`
 * sibling, so `tests/frontend/reading-telemetry.test.mjs` can exercise it
 * without a browser. Everything left in this file is `document`/`window`/
 * `IntersectionObserver` wiring, which `e2e/reading-telemetry.spec.ts` proves.
 */

const TELEMETRY_URL = "/api/telemetry";
const TICK_MS = 1_000;

const ACTIVITY_EVENTS = [
  "pointermove",
  "pointerdown",
  "keydown",
  "wheel",
  "scroll",
  "touchstart",
] as const;

function createImpressionId(): string | null {
  try {
    const randomUUID = globalThis.crypto?.randomUUID;
    return typeof randomUUID === "function" ? randomUUID.call(globalThis.crypto) : null;
  } catch {
    return null;
  }
}

export function ReadingTelemetry({ reviewId }: { reviewId: string }): null {
  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const maybeImpressionId = createImpressionId();
    if (!maybeImpressionId) return undefined;
    const impressionId = maybeImpressionId;
    const accumulator = new ReadingAccumulator(floorNow(performance.now()));

    // Tracked mirrors, not live DOM reads. A transition handler must advance
    // the accumulator with the gates that applied BEFORE the transition, and
    // `document.visibilityState`/`document.hasFocus()` have already changed
    // to the new value by the time their event fires — reading them live
    // inside a handler would silently attribute the whole preceding interval
    // to the new state instead of the old one.
    let visible = document.visibilityState === "visible";
    let focused = document.hasFocus();
    let bodyVisible = false;

    const sentThresholds = new Set<number>([0]);
    let checkpointsSent = 0;
    let lastSent: ReadingTelemetryPayload | null = null;
    let intervalId: ReturnType<typeof setInterval> | undefined;
    let observer: IntersectionObserver | undefined;
    let stopped = false;

    function gates(): ActivityGates {
      // `recentlyActive` is always true here on purpose. The accumulator
      // already clips active time to `lastActivityMs + IDLE_MS` internally
      // (Task 6) whenever real activity actually occurred; recomputing a
      // second, coarser idle boolean per tick and passing it as this gate
      // would double-apply the freshness window at tick granularity instead
      // of the accumulator's continuous one, which is exactly the "dropped
      // fresh prefix" failure mode this task's binding update warns against.
      // The only thing that keeps a stale reader from accruing time is NOT
      // calling `noteActivity()` — visible/focused/bodyVisible remain real
      // gates because nothing else tracks them.
      return { visible, focused, recentlyActive: true, bodyVisible };
    }

    function send(payload: ReadingTelemetryPayload): void {
      let body: string;
      try {
        body = JSON.stringify(payload);
      } catch {
        return;
      }

      let sent = false;
      try {
        sent =
          typeof navigator.sendBeacon === "function" &&
          navigator.sendBeacon(TELEMETRY_URL, new Blob([body], { type: "application/json" }));
      } catch {
        // A throwing capability is the same as an unavailable one: continue
        // to the keepalive fallback rather than losing the checkpoint.
      }

      if (!sent) {
        try {
          // Never awaited: a slow or failed telemetry write must not hold up
          // anything, and its rejection must not surface anywhere.
          void fetch(TELEMETRY_URL, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body,
            keepalive: true,
          }).catch(() => {});
        } catch {
          // Telemetry failures must never throw into product code.
        }
      }
      checkpointsSent += 1;
      lastSent = payload;
    }

    function attemptFlush(): void {
      const current = accumulator.payload(impressionId, reviewId, checkpointsSent);
      if (!shouldFlush(checkpointsSent, current.active_ms, current, lastSent)) return;
      send(current);
    }

    function noteInteractionAndFlush(kind: InteractionKind): void {
      accumulator.noteInteraction(kind, floorNow(performance.now()));
      attemptFlush();
    }

    function teardownResources(): void {
      if (intervalId !== undefined) clearInterval(intervalId);
      intervalId = undefined;
      try {
        observer?.disconnect();
      } catch {
        // A partially constructed observer must not prevent listener cleanup.
      }
      observer = undefined;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("pagehide", onPageHide);
      for (const type of ACTIVITY_EVENTS) {
        window.removeEventListener(type, type === "scroll" ? onScroll : onActivity);
      }
      window.removeEventListener(TELEMETRY_EVENT, onInteractionEvent as EventListener);
      document.removeEventListener("click", onDocumentClick);
    }

    function finish(): void {
      if (stopped) return;
      stopped = true;

      // React cleanup is a terminal lifecycle boundary too. Advance under the
      // gates that were current on this page, then make one ordinary
      // changed/budgeted/floored flush attempt before resources disappear.
      try {
        accumulator.advance(floorNow(performance.now()), gates());
        attemptFlush();
      } catch {
        // Cleanup must remain fail-open even if a browser clock API is hostile.
      }
      teardownResources();
    }

    function onVisibilityChange(): void {
      accumulator.advance(floorNow(performance.now()), gates());
      visible = document.visibilityState === "visible";
      if (!visible) attemptFlush();
    }

    function onFocus(): void {
      accumulator.advance(floorNow(performance.now()), gates());
      focused = true;
    }

    function onBlur(): void {
      accumulator.advance(floorNow(performance.now()), gates());
      focused = false;
    }

    function onPageHide(): void {
      accumulator.advance(floorNow(performance.now()), gates());
      visible = false;
      attemptFlush();
    }

    function onActivity(): void {
      accumulator.noteActivity(floorNow(performance.now()), gates());
    }

    function onScroll(): void {
      onActivity();
      const body = document.getElementById("review-body");
      if (body) {
        accumulator.noteScroll(scrollProgress(body.getBoundingClientRect(), window.innerHeight));
      }
    }

    function onInteractionEvent(event: Event): void {
      const detail = (event as CustomEvent<InteractionDetail>).detail;
      if (!detail || detail.reviewId !== reviewId) return;
      noteInteractionAndFlush(detail.kind);
    }

    function onDocumentClick(event: MouseEvent): void {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest("a[data-telemetry-outlink]");
      if (!anchor) return;
      if (anchor.getAttribute("data-telemetry-review-id") !== reviewId) return;
      noteInteractionAndFlush("outlink");
    }

    try {
      const bodyEl = document.getElementById("review-body");
      if (bodyEl && typeof IntersectionObserver === "function") {
        observer = new IntersectionObserver(
          ([entry]) => {
            accumulator.advance(floorNow(performance.now()), gates());
            bodyVisible = entry.isIntersecting;
          },
          { threshold: 0 },
        );
        observer.observe(bodyEl);
      }

      document.addEventListener("visibilitychange", onVisibilityChange);
      window.addEventListener("focus", onFocus);
      window.addEventListener("blur", onBlur);
      window.addEventListener("pagehide", onPageHide);
      for (const type of ACTIVITY_EVENTS) {
        window.addEventListener(type, type === "scroll" ? onScroll : onActivity, { passive: true });
      }
      window.addEventListener(TELEMETRY_EVENT, onInteractionEvent as EventListener);
      document.addEventListener("click", onDocumentClick);

      // The start checkpoint (design §4.2): unawaited, fired before any
      // interaction can occur, so even a sub-second bounce leaves a
      // server-owned `started_at`. It counts toward the budget immediately —
      // there is no response to wait for before deciding whether the NEXT
      // write is still allowed.
      send(accumulator.payload(impressionId, reviewId, 0));

      intervalId = setInterval(() => {
        const now = floorNow(performance.now());
        accumulator.advance(now, gates());
        const current = accumulator.payload(impressionId, reviewId, checkpointsSent);

        if (current.wall_ms >= MAX_SESSION_MS) {
          // The approved ceiling. `finish` is idempotent, so React's later
          // cleanup cannot emit a second terminal checkpoint.
          finish();
          return;
        }

        const threshold = nextCheckpoint(current.active_ms, sentThresholds, checkpointsSent);
        if (threshold !== null) {
          // One cumulative write represents every threshold already crossed.
          // Consume all of them now so later ticks cannot produce delayed
          // catch-up sends, while still emitting exactly once on this tick.
          let crossed: number | null = threshold;
          while (crossed !== null) {
            sentThresholds.add(crossed);
            crossed = nextCheckpoint(current.active_ms, sentThresholds, checkpointsSent);
          }
          send(current);
        }
      }, TICK_MS);
    } catch {
      // Missing or throwing browser capabilities disable this impression.
      // Remove anything registered before the failure and leave the page UI
      // untouched; no telemetry failure is user-visible.
      stopped = true;
      teardownResources();
      return undefined;
    }

    return finish;
    // reviewId is the only prop, and it is also the only thing that should
    // ever restart this lifecycle: a new id is a new impression, with its own
    // accumulator and its own started_at. Every other value referenced above
    // is a closure-local constant for the lifetime of one effect run.
  }, [reviewId]);

  return null;
}

export default ReadingTelemetry;
