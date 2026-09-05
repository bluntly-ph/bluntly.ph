import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

// Not imported from the fixture server module: Playwright's TS transform for
// spec files does not interoperate with that file's `import.meta` guard
// (`Cannot use 'import.meta' outside a module`) when required through its
// CJS-facing loader. Duplicated here as plain literals instead — the fixture
// server file is the single source of truth for what these ids actually
// resolve to; if they drift, `page.goto` / the related-review link assertions
// fail immediately and visibly.
const REVIEW_A = "aaaaaaaa-0000-4000-8000-000000000001";
const REVIEW_B = "bbbbbbbb-0000-4000-8000-000000000002";

/**
 * Task 7 acceptance: the review-page reading lifecycle, against a real page
 * and real browser wiring.
 *
 * Run with the dedicated config, not the default one:
 *
 *   npx playwright test --config=playwright.reading-telemetry.config.ts
 *
 * See that config and e2e/fixtures/reading-telemetry-fixture-server.mjs for
 * exactly what is real here (the page, the React tree, the client) and what
 * is fixtured (one backend endpoint) and why.
 *
 * Every assertion is on a REQUEST BODY intercepted at `/api/telemetry`, never
 * on an internal call count — the same convention this suite's README states
 * for `console-health.spec.ts`: observable behaviour, not implementation.
 */

type Body = {
  impression_id: string;
  review_id: string;
  seq: number;
  active_ms: number;
  body_active_ms: number;
  wall_ms: number;
  scroll_pct: number;
  vote_after_ms: number | null;
  report_after_ms: number | null;
  comment_after_ms: number | null;
  share_after_ms: number | null;
  photo_after_ms: number | null;
  outlink_after_ms: number | null;
};

const REVIEW_PATH = `/reviews/${REVIEW_A}`;

/** Overrides `document.visibilityState`/`hasFocus` with test-controlled
 * values, exposed as `window.__setVisible`/`__setFocused`. Pure Playwright
 * page-script injection — nothing is added to the app itself. */
async function installVisibilityControl(page: Page): Promise<void> {
  await page.addInitScript(() => {
    let visible = true;
    let focused = true;
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => (visible ? "visible" : "hidden"),
    });
    document.hasFocus = () => focused;
    (window as unknown as Record<string, unknown>).__setVisible = (v: boolean) => {
      visible = v;
      document.dispatchEvent(new Event("visibilitychange"));
    };
    (window as unknown as Record<string, unknown>).__setFocused = (v: boolean) => {
      focused = v;
      window.dispatchEvent(new Event(v ? "focus" : "blur"));
    };
  });
}

type VisibilityTestWindow = Window & {
  __setVisible: (value: boolean) => void;
  __setFocused: (value: boolean) => void;
};

function setVisible(page: Page, value: boolean) {
  return page.evaluate((v) => (window as unknown as VisibilityTestWindow).__setVisible(v), value);
}

function setFocused(page: Page, value: boolean) {
  return page.evaluate((v) => (window as unknown as VisibilityTestWindow).__setFocused(v), value);
}

/** Captures every `/api/telemetry` request body, in arrival order, and
 * answers with the given status. `respond: null` simulates a hard failure. */
function captureTelemetry(page: Page, status: number | null) {
  const bodies: Body[] = [];
  const attach = page.route("**/api/telemetry", async (route: Route) => {
    const raw = route.request().postDataJSON() as Body | null;
    if (raw) bodies.push(raw);
    if (status === null) {
      await route.abort("failed");
    } else {
      await route.fulfill({ status, contentType: "text/plain", body: "" });
    }
  });
  return { bodies, ready: attach };
}

/**
 * The mount checkpoint's surviving impression id for `reviewId`.
 *
 * `next dev` runs React Strict Mode, which deliberately double-invokes a
 * component's effect on mount (setup → cleanup → setup) to surface missing
 * cleanup — a React-documented development behaviour, not a defect, and one
 * the production build never exhibits. Because the mount checkpoint is fired
 * unawaited from inside the effect body, the FIRST invocation's beacon is
 * already in flight before its own cleanup can prevent it, so two seq-0
 * bodies for the same review can legitimately arrive. Only the SECOND
 * mount's listeners/interval are still alive afterwards — the first's
 * cleanup already removed them — so every later assertion must track that
 * surviving impression specifically, never "the first body seen".
 */
async function survivingImpression(page: Page, bodies: Body[], reviewId: string): Promise<string> {
  await expect.poll(() => bodies.some((b) => b.review_id === reviewId && b.seq === 0)).toBe(true);
  // Real wall-clock wait (Playwright's own timeout, not the page's fake
  // clock) so a second Strict-Mode invocation already in flight has time to
  // land before we decide which one is the survivor.
  await page.waitForTimeout(300);
  const starts = bodies.filter((b) => b.review_id === reviewId && b.seq === 0);
  return starts[starts.length - 1].impression_id;
}

function forImpression(bodies: Body[], impressionId: string): Body[] {
  return bodies.filter((b) => b.impression_id === impressionId);
}

/**
 * Freezes the fake clock at (approximately) the current instant, after
 * letting page load/hydration run with the clock ticking normally — per
 * Playwright's own guidance for `clock.install`.
 *
 * A single `pauseAt(Date.now())` reliably races itself: the value is read
 * over one round trip and applied over a second, and the real clock (still
 * running until the moment `pauseAt` actually executes) has usually already
 * passed it by the time it arrives, which `pauseAt` refuses ("Cannot
 * fast-forward to the past"). A small forward buffer, retried if still too
 * late, is what actually converges.
 */
async function freezeClockNow(page: Page): Promise<void> {
  let bufferMs = 50;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const target = (await page.evaluate(() => Date.now())) + bufferMs;
    try {
      await page.clock.pauseAt(target);
      return;
    } catch {
      bufferMs *= 4;
    }
  }
  throw new Error("freezeClockNow: could not pause the fake clock");
}

test.describe("reading telemetry — lifecycle and fail-open", () => {
  test("forced telemetry failures preserve rendering and the vote control", async ({ page }) => {
    const { bodies, ready } = captureTelemetry(page, 500);
    await ready;

    const pageErrors: Error[] = [];
    page.on("pageerror", (e) => pageErrors.push(e));

    await page.goto(REVIEW_PATH);

    // The mount checkpoint still fires and is still observed, even though
    // every response it gets back is a 500 — the send is fire-and-forget.
    await expect.poll(() => bodies.length).toBeGreaterThan(0);
    expect(bodies[0].seq).toBe(0);

    // The heading and the vote control render — a telemetry outage must not
    // be able to blank the page or disable an unrelated control.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const helpful = page.getByRole("button", { name: /helpful/i }).first();
    await expect(helpful).toBeVisible();
    await expect(helpful).toBeEnabled();

    // Clicking it must still run to completion. Signed out, that means the
    // login redirect fires — proof the click handler executed rather than
    // throwing, with telemetry failing on every request the whole time.
    await helpful.click();
    await expect(page).toHaveURL(/\/login\?next=/);

    expect(pageErrors, `unexpected page errors: ${pageErrors.map(String).join("; ")}`).toHaveLength(0);
  });

  test("the first body is sequence zero; later bodies are sparse and cumulative", async ({ page }) => {
    const { bodies, ready } = captureTelemetry(page, 204);
    await ready;
    // Per Playwright's own guidance: install and navigate with the clock
    // running normally, so page load/hydration timers are not starved, THEN
    // pause. `install` alone still drifts with real wall-clock time after
    // that ("Date.now will progress as the timers fire") — only `pauseAt`
    // actually freezes it, which matters here because the dedup assertions
    // below rely on zero elapsed time between two `evaluate` calls with no
    // `fastForward` between them; `wall_ms` is monotonic and un-floored, so
    // even a few milliseconds of real drift reads as "changed".
    await page.clock.install({ time: 0 });
    await page.goto(REVIEW_PATH);
    await freezeClockNow(page);
    const impressionId = await survivingImpression(page, bodies, REVIEW_A);
    const mine = () => forImpression(bodies, impressionId);
    expect(mine()[0]).toMatchObject({ seq: 0, active_ms: 0, body_active_ms: 0, wall_ms: 0 });

    // One real interaction so the accumulator has something to accrue
    // against real elapsed time. Two SEPARATE jumps, not one 31-second one:
    // a frozen fake clock fires a repeating interval only once per
    // `fastForward` call, however many virtual periods it spans — which is
    // this component's own "no catch-up bursts" rule (a single tick jumped
    // forward a long way emits exactly one checkpoint, never one per
    // threshold it happened to cross), so crossing two thresholds honestly
    // needs two ticks, exactly as it would in a real unsuspended tab.
    await page.mouse.move(200, 200);
    await page.clock.fastForward(10_000);
    await expect.poll(() => mine().length).toBe(2);
    await page.clock.fastForward(21_000);

    // Sparse: two more thresholds crossed (10s, 30s) — not thirty-one
    // one-per-second writes, and not one per elapsed second of any kind.
    await expect.poll(() => mine().length).toBe(3);
    expect(mine()[1].seq).toBe(1);
    expect(mine()[2].seq).toBe(2);

    // Cumulative, not delta: each later body's active/wall time is at least
    // the previous body's, never a reset-to-zero per-interval count.
    expect(mine()[1].active_ms).toBeGreaterThanOrEqual(10_000);
    expect(mine()[2].active_ms).toBeGreaterThanOrEqual(mine()[1].active_ms);
    expect(mine()[2].wall_ms).toBeGreaterThanOrEqual(mine()[1].wall_ms);
  });

  test("hidden, unfocused, and idle intervals do not advance active time", async ({ page }) => {
    await installVisibilityControl(page);
    const { bodies, ready } = captureTelemetry(page, 204);
    await ready;
    // Per Playwright's own guidance: install and navigate with the clock
    // running normally, so page load/hydration timers are not starved, THEN
    // pause. `install` alone still drifts with real wall-clock time after
    // that ("Date.now will progress as the timers fire") — only `pauseAt`
    // actually freezes it, which matters here because the dedup assertions
    // below rely on zero elapsed time between two `evaluate` calls with no
    // `fastForward` between them; `wall_ms` is monotonic and un-floored, so
    // even a few milliseconds of real drift reads as "changed".
    await page.clock.install({ time: 0 });
    await page.goto(REVIEW_PATH);
    await freezeClockNow(page);
    const impressionId = await survivingImpression(page, bodies, REVIEW_A);
    const mine = () => forImpression(bodies, impressionId);

    // Hidden: no active time at all, however long elapses.
    await setVisible(page, false);
    await page.clock.fastForward(20_000);
    await setVisible(page, true);

    // Unfocused: same guarantee — still zero, even though the tab is visible
    // again by this point.
    await setFocused(page, false);
    await page.clock.fastForward(20_000);
    await setFocused(page, true);

    // NOW genuinely visible, focused, and active: a real signal refreshes the
    // freshness window at this instant (~t=40s), and eleven seconds of real
    // accrual follows — crossing the first periodic threshold.
    await page.mouse.move(120, 120);
    await page.clock.fastForward(11_000);
    await expect.poll(() => mine().length).toBeGreaterThanOrEqual(2);

    const last = mine()[mine().length - 1];
    // The 40 seconds spent hidden/unfocused contributed nothing: active time
    // reflects only the ~11s that followed the refresh, not 40s + 11s.
    expect(last.active_ms).toBeLessThan(20_000);
    expect(last.active_ms).toBeGreaterThanOrEqual(10_000);
    // Wall time is unconditional and keeps counting through all of it.
    expect(last.wall_ms).toBeGreaterThanOrEqual(51_000);
  });

  test("scroll bodies contain only monotonic legal milestones", async ({ page }) => {
    const { bodies, ready } = captureTelemetry(page, 204);
    await ready;

    await page.goto(REVIEW_PATH);
    const impressionId = await survivingImpression(page, bodies, REVIEW_A);
    const mine = () => forImpression(bodies, impressionId);

    // No fake clock in this test — real IntersectionObserver settling and
    // real scroll events are what is under test. The MIN_ACTIVE_MS floor
    // (design §4.5) refuses any post-start checkpoint below 1s of accumulated
    // active time, so this first wait clears that floor before the loop
    // starts asking for checkpoints at all.
    await page.mouse.move(10, 10);
    await page.waitForTimeout(1_200);

    const steps = [0.2, 0.4, 0.6, 0.8, 1];
    for (const fraction of steps) {
      await page.evaluate((f) => {
        window.scrollTo(0, Math.floor(document.documentElement.scrollHeight * f));
      }, fraction);
      await page.waitForTimeout(150);
      // A checkpoint only exists at start/threshold/terminal boundaries, so
      // force one to observe the milestone reached so far. A pagehide with
      // nothing new since the last send is a correct no-op (see the
      // dedicated dedup test), so not every dispatch need produce a row —
      // this wait only lets one that DOES fire cross the IPC hop into
      // `bodies` before the next iteration's scroll.
      await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
      await page.waitForTimeout(200);
    }

    const scrolls = mine().map((b) => b.scroll_pct);
    const LEGAL = new Set([0, 25, 50, 75, 100]);
    for (const value of scrolls) {
      expect(LEGAL.has(value), `${value} is not a legal scroll milestone`).toBe(true);
    }
    for (let i = 1; i < scrolls.length; i += 1) {
      expect(scrolls[i]).toBeGreaterThanOrEqual(scrolls[i - 1]);
    }
    expect(scrolls[scrolls.length - 1]).toBe(100);
  });

  test("pagehide flushes only changed state, once, under the checkpoint cap", async ({ page }) => {
    const { bodies, ready } = captureTelemetry(page, 204);
    await ready;
    // Per Playwright's own guidance: install and navigate with the clock
    // running normally, so page load/hydration timers are not starved, THEN
    // pause. `install` alone still drifts with real wall-clock time after
    // that ("Date.now will progress as the timers fire") — only `pauseAt`
    // actually freezes it, which matters here because the dedup assertions
    // below rely on zero elapsed time between two `evaluate` calls with no
    // `fastForward` between them; `wall_ms` is monotonic and un-floored, so
    // even a few milliseconds of real drift reads as "changed".
    await page.clock.install({ time: 0 });
    await page.goto(REVIEW_PATH);
    await freezeClockNow(page);
    const impressionId = await survivingImpression(page, bodies, REVIEW_A);
    const mine = () => forImpression(bodies, impressionId);

    await page.mouse.move(100, 100);
    await page.clock.fastForward(11_000);
    // `fastForward` resolves once the page's own script has run; the
    // intercepted request still has to cross the IPC boundary into this
    // route handler, which is a separate async hop `expect.poll` absorbs.
    await expect.poll(() => mine().length).toBeGreaterThanOrEqual(2);
    const afterThreshold = mine().length;

    // New state since the last send (more elapsed active time) — pagehide
    // must flush it exactly once.
    await page.mouse.move(150, 150);
    await page.clock.fastForward(2_000);
    await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
    await expect.poll(() => mine().length).toBe(afterThreshold + 1);

    // Nothing changed since that flush — a second pagehide must be a no-op,
    // not a duplicate write of the same state.
    await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
    await page.waitForTimeout(100);
    expect(mine().length).toBe(afterThreshold + 1);

    // The shared budget still holds: never more than sixteen writes total for
    // one impression, whatever mix of periodic and terminal writes produced
    // them.
    expect(mine().length).toBeLessThanOrEqual(16);
  });

  test("navigating away and back creates one fresh listener set, not duplicate requests", async ({
    page,
  }) => {
    const { bodies, ready } = captureTelemetry(page, 204);
    await ready;
    // Per Playwright's own guidance: install and navigate with the clock
    // running normally, so page load/hydration timers are not starved, THEN
    // pause. `install` alone still drifts with real wall-clock time after
    // that ("Date.now will progress as the timers fire") — only `pauseAt`
    // actually freezes it, which matters here because the dedup assertions
    // below rely on zero elapsed time between two `evaluate` calls with no
    // `fastForward` between them; `wall_ms` is monotonic and un-floored, so
    // even a few milliseconds of real drift reads as "changed".
    await page.clock.install({ time: 0 });
    await page.goto(REVIEW_PATH);
    await freezeClockNow(page);
    const firstImpression = await survivingImpression(page, bodies, REVIEW_A);

    // A real in-app navigation, not a synthetic one: the sidebar's own
    // "Related reviews" link, which the fixture backend populates with the
    // other fixture review specifically so this is possible.
    //
    // The clock is resumed for the transition itself: React's and Next's own
    // internal scheduling for a client-side route change is not something
    // this test controls or should assume about, and leaving the clock
    // frozen across it risks starving that scheduling rather than testing
    // anything about the reading lifecycle. It is re-frozen once the new
    // page has actually mounted, for the same deterministic-interval reasons
    // as everywhere else in this file.
    await page.clock.resume();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("link", { name: new RegExp(REVIEW_B.slice(0, 8)) }).click();
    await expect(page).toHaveURL(new RegExp(REVIEW_B));
    const onB = await survivingImpression(page, bodies, REVIEW_B);
    expect(onB).not.toBe(firstImpression);
    await freezeClockNow(page);

    // Nothing from the FIRST impression fires again while away — the effect
    // that owned it was torn down (by React unmounting the old page tree, a
    // real client-side route change here), not merely joined by a new one.
    const seenWhileOnB = forImpression(bodies, firstImpression).length;
    await page.clock.fastForward(11_000);
    expect(forImpression(bodies, firstImpression)).toHaveLength(seenWhileOnB);

    // Back to the original review: a fresh start payload for review A, whose
    // impression id differs from the one that left. Resume/re-freeze around
    // this transition for the same reason as the forward navigation above.
    await page.clock.resume();
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(REVIEW_A));
    const secondVisit = await survivingImpression(page, bodies, REVIEW_A);
    expect(secondVisit).not.toBe(firstImpression);
    await freezeClockNow(page);

    // And exactly one interval is now running for the returned page — a
    // leaked interval from an earlier mount would double every count from
    // here on, because two timers would both be advancing the same fake
    // clock and both attempting a send at the same threshold.
    const mine = () => forImpression(bodies, secondVisit);
    const beforeTick = mine().length;
    await page.mouse.move(50, 50);
    await page.clock.fastForward(11_000);
    await expect.poll(() => mine().length).toBe(beforeTick + 1);
  });
});
