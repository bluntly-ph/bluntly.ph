import { test, expect } from "@playwright/test";

/**
 * Gate 3: does the page actually run once it reaches the browser?
 *
 * A React component that throws during render still compiles, still lints, and
 * still returns HTTP 200 behind an error boundary. The only signal that
 * separates "served" from "working" is what the browser reports, so these tests
 * assert on console errors and page exceptions rather than status codes.
 */

/** Noise that is expected in dev and says nothing about page health. */
const IGNORED = [
  /Download the React DevTools/i,
  /\[Fast Refresh\]/i,
  /Redis|rate limiter/i,
  // Next dev streams HMR over a websocket that closes on navigation.
  /WebSocket connection to .*_next\/webpack-hmr/i,
  // FIREFOX ONLY, AND NOT OURS. Supabase Storage is fronted by Cloudflare,
  // which sets `__cf_bm` on image responses; Firefox rejects it as a
  // cross-site cookie and reports the rejection as a JavaScript error, once
  // per image. Chromium and WebKit say nothing. The images load either way —
  // the content and styling assertions below pass on all three engines.
  //
  // Ignored rather than fixed because there is nothing here to fix: the cookie
  // is set by a third-party CDN on a host we do not control. Avoiding it would
  // mean proxying every product image through our own origin, which is a
  // serving change, not a console fix. Deliberately narrow — it matches this
  // one cookie name, so a real storage error still fails the gate.
  /Cookie .__cf_bm. has been rejected for invalid domain/i,
  // DEV ONLY, AND DELIBERATE — DO NOT "FIX" BY LOOSENING THE CSP.
  // next.config.ts omits `unsafe-eval` from script-src on purpose. React's
  // development build uses eval() for debugging aids and complains when it is
  // blocked; the production build never calls eval(), so this cannot occur in
  // prod. Adding `unsafe-eval` to silence it would trade a real XSS mitigation
  // for a quieter dev console.
  /eval\(\) is not supported in this environment/i,
];

const PAGES = ["/", "/search", "/questions", "/requests", "/about"] as const;

/** Long enough for a hydration error to surface, short enough to stay cheap. */
const HYDRATION_SETTLE_MS = 1500;

for (const path of PAGES) {
  test(`${path} loads with no console errors or uncaught exceptions`, async ({ page }) => {
    const errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() !== "error") return;
      const text = msg.text();
      if (IGNORED.some((re) => re.test(text))) return;
      errors.push(`console.error: ${text}`);
    });
    page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));

    // NOT `networkidle`. Next's router prefetches the destinations of visible
    // links, Chrome gives those requests the lowest priority, and on a page
    // that is otherwise finished they simply sit there — so the network never
    // goes idle and the test times out at 30s having asserted nothing. Against
    // localhost the prefetches resolve instantly and it happened to work;
    // against a deployed origin, five of these seven tests failed on a site
    // whose load event fires in 564ms with zero console errors. Playwright
    // discourages `networkidle` for exactly this reason.
    await page.goto(path);
    await page.waitForLoadState("domcontentloaded");

    // Hydration errors arrive just after load rather than during it, so there
    // has to be a wait of some kind. A short fixed one is honest about what it
    // is: there is no event for "React finished and did not throw".
    await page.waitForTimeout(HYDRATION_SETTLE_MS);

    expect(errors, `${path} reported browser errors`).toEqual([]);
  });
}

test("the home page renders real content, not an empty shell", async ({ page }) => {
  await page.goto("/");

  // Hydration failures and error boundaries both produce a near-empty body.
  //
  // Polled rather than read once. `goto` resolves on `load`, but the App Router
  // streams the page: the shell arrives first and the content fills in after,
  // so a single read races the stream. Measured against production it caught
  // 15 characters on one run in three and 1874 on the others — a flaky gate,
  // which is worse than no gate, because it teaches everyone to re-run it.
  //
  // Same fault as the `networkidle` wait above, which was fixed and this was
  // not. Polling keeps the assertion identical and lets it settle.
  await expect
    .poll(async () => (await page.locator("body").innerText()).trim().length, {
      message: "home page body should not be effectively empty",
    })
    .toBeGreaterThan(200);
});

test("styles are actually applied", async ({ page }) => {
  await page.goto("/");
  // Checking for a stylesheet URL is unreliable — dev and prod serve CSS from
  // different paths. Ask the browser what it computed instead.
  const bg = await page.evaluate(() =>
    getComputedStyle(document.body).backgroundColor,
  );
  expect(bg, "body should have a resolved background colour").not.toBe("");
  expect(bg).not.toBe("rgba(0, 0, 0, 0)");
});
