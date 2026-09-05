import { defineConfig, devices } from "@playwright/test";

/**
 * A dedicated config for ONE spec: e2e/reading-telemetry.spec.ts.
 *
 * WHY NOT THE MAIN playwright.config.ts. That config's `webServer` runs
 * `npm run dev:all`, which starts the real FastAPI backend against a real
 * Postgres. This environment has no reachable local Postgres, so that server
 * never comes up here. Rather than fake the whole backend or, worse, replace
 * the lifecycle under test with something that isn't the real component tree,
 * this config starts:
 *
 *   1. a narrow local fixture backend (e2e/fixtures/reading-telemetry-fixture-
 *      server.mjs) that answers exactly the one call the review page cannot
 *      render without — see that file's header for the exact scope and limit;
 *   2. `next dev` on a different port, pointed at that fixture via `API_URL`.
 *
 * Everything downstream — the review page, its Server Components, the BFF
 * proxy, `ReadingTelemetry.tsx`, the six components it instruments — is the
 * REAL production code, unmodified for the test. Only the data source
 * underneath one endpoint is swapped, exactly as `API_URL` already exists to
 * allow.
 *
 * Chromium only, and one worker: this spec asserts on exact request
 * sequences and fake-clock timing, which is what needs proving here, not
 * cross-browser rendering (already covered by the rest of the suite against a
 * real stack). Parallel workers sharing the same fixture port would also
 * simply be wrong.
 *
 * Run: `npx playwright test --config=playwright.reading-telemetry.config.ts`
 */

const WEB_PORT = 3100;
const FIXTURE_PORT = 8010;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "reading-telemetry.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,

  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
      command: `node e2e/fixtures/reading-telemetry-fixture-server.mjs`,
      url: `http://localhost:${FIXTURE_PORT}/api/v1/reviews/aaaaaaaa-0000-4000-8000-000000000001/full`,
      env: { FIXTURE_PORT: String(FIXTURE_PORT) },
      reuseExistingServer: false,
      timeout: 15_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // A distinct port so this never collides with a `npm run dev:all` stack
      // a developer already has running on 3000 for other suites.
      command: `npx next dev --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/reviews/aaaaaaaa-0000-4000-8000-000000000001`,
      env: {
        API_URL: `http://localhost:${FIXTURE_PORT}`,
        NEXT_PUBLIC_API_URL: `http://localhost:${FIXTURE_PORT}`,
        TELEMETRY_INGEST_KEY: "reading-telemetry-e2e-fixture-key",
      },
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
