import assert from "node:assert/strict";
import test from "node:test";

import { markInteraction, TELEMETRY_EVENT } from "../../lib/reading-telemetry-events.ts";

test("is an SSR no-op when window is unavailable", () => {
  const originalWindow = globalThis.window;
  try {
    delete globalThis.window;
    assert.doesNotThrow(() => markInteraction("review-a", "vote"));
  } finally {
    globalThis.window = originalWindow;
  }
});

test("dispatches a namespaced CustomEvent with only the matching review detail", () => {
  const originalWindow = globalThis.window;
  const target = new EventTarget();
  const received = [];
  try {
    globalThis.window = target;
    target.addEventListener(TELEMETRY_EVENT, (event) => {
      const detail = event.detail;
      if (detail.reviewId === "review-a") received.push({ event, detail });
    });

    markInteraction("review-b", "report");
    markInteraction("review-a", "share");

    assert.equal(received.length, 1);
    assert.ok(received[0].event instanceof CustomEvent);
    assert.deepEqual(Object.keys(received[0].detail).sort(), ["kind", "reviewId"]);
    assert.deepEqual(received[0].detail, { reviewId: "review-a", kind: "share" });
  } finally {
    globalThis.window = originalWindow;
  }
});
