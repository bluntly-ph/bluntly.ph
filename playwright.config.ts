import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the bluntly.ph frontend.
 *
 * These tests need BOTH servers — web :3000 and API :8000 — because every page
 * is server-rendered against the backend. `npm run dev:all` starts the pair
 * idempotently; `reuseExistingServer` means a stack you already have up is used
 * as-is rather than being torn down and restarted under you.
 *
 * Scope note: the app's forms (product search, review composer, ask-a-question)
 * all sit behind an email-OTP login, which cannot be driven end-to-end without a
 * mail hook. So this suite covers what is reachable signed-out — the route-guard
 * matrix, public page rendering, and console health. Extending past that needs a
 * test-only session endpoint or a seeded token; see e2e/README.md.
 */
/**
 * Point the suite at a deployed environment instead of localhost:
 *
 *   PLAYWRIGHT_BASE_URL=https://www.bluntly.ph npx playwright test \
 *     e2e/console-health.spec.ts e2e/accessibility.spec.ts --project=chromium
 *
 * Useful when there is no local database — the pages here are server-rendered
 * against the API, so without one the local stack renders empty states and the
 * suite tests nothing. It is also the only way to check that what is *deployed*
 * renders, which is a different question from whether the working tree does.
 *
 * Only run the read-only specs this way. `route-guards.spec.ts` submits forms,
 * and production is not a fixture.
 */
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const IS_REMOTE = !BASE_URL.includes("localhost");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",

  // WebKit on Windows crashes its worker (STATUS_STACK_BUFFER_OVERRUN,
  // 0xC0000409) under Playwright's default parallelism — the browser dies, not
  // the app, and it takes ~20 unrelated tests down with it as "worker process
  // exited unexpectedly". The same specs pass 37/37 serially. Capping workers on
  // Windows keeps the matrix honest; other platforms keep the default (one
  // worker per core).
  workers: process.platform === "win32" ? 2 : undefined,

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    // Guards must be observed, not followed — a 307 that silently lands on /login
    // is indistinguishable from a correct one once the redirect is applied.
    ignoreHTTPSErrors: true,
  },

  // Cross-browser + mobile matrix (M3). The three desktop engines cover the
  // rendering families that matter — Blink, Gecko, WebKit — and the two mobile
  // profiles pin the viewports the responsive layout is designed around: a
  // small Android (393px) and iOS Safari (393px, but WebKit's viewport and
  // safe-area behaviour differ enough to be worth its own run).
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
    { name: "mobile-safari", use: { ...devices["iPhone 14"] } },
  ],

  // Starting a local stack would be pointless when the target is deployed, and
  // worse than pointless: it would bind ports and wait three minutes first.
  webServer: IS_REMOTE
    ? undefined
    : {
        command: "npm run dev:all",
        url: "http://localhost:3000/welcome",
        reuseExistingServer: true,
        timeout: 180_000,
        stdout: "ignore",
        stderr: "pipe",
      },
});
