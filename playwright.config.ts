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
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    // Guards must be observed, not followed — a 307 that silently lands on /login
    // is indistinguishable from a correct one once the redirect is applied.
    ignoreHTTPSErrors: true,
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: {
    command: "npm run dev:all",
    url: "http://localhost:3000/welcome",
    reuseExistingServer: true,
    timeout: 180_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
