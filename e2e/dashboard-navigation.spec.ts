import { expect, test } from "@playwright/test";

/**
 * Earnings navigation that only a signed-in account can reach.
 *
 * History's "Historical Bill" pill was a span drawn as a button, going nowhere.
 * It now opens Payment history on /dashboard — and /dashboard streams in behind
 * its loading.tsx, so the browser's own jump to `#history` found only the
 * skeleton and the reader landed 1,955px above the section (390px, measured
 * 2026-09-17). components/dashboard/ScrollToHash.tsx closes that.
 *
 * A moderator is a signed-in, onboarded account, so the moderator session the
 * console specs use opens these screens too:
 *   E2E_MODERATOR_TOKEN=<token> npx playwright test e2e/dashboard-navigation.spec.ts
 *
 * Never point this at production.
 */

const TOKEN = process.env.E2E_MODERATOR_TOKEN;

test.describe("earnings navigation", () => {
  test.skip(
    !TOKEN,
    "E2E_MODERATOR_TOKEN is not set — needs the isolated test environment (see the file header).",
  );

  test.beforeEach(async ({ context }) => {
    await context.addCookies([{
      name: "bluntly_session",
      value: TOKEN as string,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    }]);
  });

  test("Historical Bill opens Payment history in view", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard/history");
    await Promise.all([
      page.waitForURL("**/dashboard#history", { waitUntil: "load" }),
      page.getByRole("link", { name: "Historical Bill" }).click(),
    ]);
    const section = page.locator("#history");
    await expect(section).toBeInViewport();
  });
});
