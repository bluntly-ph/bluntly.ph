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
  // DEV ONLY, AND DELIBERATE — DO NOT "FIX" BY LOOSENING THE CSP.
  // next.config.ts omits `unsafe-eval` from script-src on purpose. React's
  // development build uses eval() for debugging aids and complains when it is
  // blocked; the production build never calls eval(), so this cannot occur in
  // prod. Adding `unsafe-eval` to silence it would trade a real XSS mitigation
  // for a quieter dev console.
  /eval\(\) is not supported in this environment/i,
];

const PAGES = ["/", "/search", "/questions", "/requests", "/about"] as const;

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

    await page.goto(path, { waitUntil: "networkidle" });

    expect(errors, `${path} reported browser errors`).toEqual([]);
  });
}

test("the home page renders real content, not an empty shell", async ({ page }) => {
  await page.goto("/");
  // Hydration failures and error boundaries both produce a near-empty body.
  const text = (await page.locator("body").innerText()).trim();
  expect(text.length, "home page body should not be effectively empty").toBeGreaterThan(200);
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
