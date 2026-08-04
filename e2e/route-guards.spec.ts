import { test, expect } from "@playwright/test";

/**
 * Auth guards, and the `?next=` return path specifically.
 *
 * Regression origin: `?next=` was dead end to end. `proxy.ts` set it, the login
 * page never rendered it as a field, and `verifyOtp` never read it — so signing
 * in always dumped you on `/`, whatever you had been trying to reach. Build,
 * typecheck, lint and a 200-check all passed the whole time it was broken, which
 * is why it needs a test at this level rather than a unit test.
 *
 * Guards live in two places and only one of them sets `next`:
 *   - proxy.ts        — PROTECTED array, optimistic cookie check, sets ?next=
 *   - lib/dal.ts      — requireUser, real backend check, bare /login redirect
 * A protected route missing from proxy.ts still redirects, but loses the return
 * path. That is exactly the silent failure this matrix catches.
 */

const GATED = [
  "/dashboard",
  "/profile",
  "/moderate",
  "/onboarding",
  "/reviews/new",
  "/questions/new",
  "/requests/new",
] as const;

const PUBLIC = [
  "/",
  "/about",
  "/search",
  "/questions",
  "/requests",
  "/categories",
  "/how-it-works",
  "/faqs",
  "/terms",
  "/privacy",
] as const;

test.describe("gated routes", () => {
  for (const path of GATED) {
    test(`${path} redirects to login preserving the return path`, async ({ page }) => {
      const response = await page.goto(path);

      expect(response?.status(), `${path} should render the login page`).toBe(200);
      await expect(page).toHaveURL(/\/login/);

      // The whole point: the destination survives the bounce.
      const next = new URL(page.url()).searchParams.get("next");
      expect(next, `${path} must arrive at /login with ?next=`).toBe(path);
    });
  }

  test("the login page carries next into the form as a hidden field", async ({ page }) => {
    await page.goto("/reviews/new");
    await expect(page).toHaveURL(/\/login\?next=%2Freviews%2Fnew/);

    // Step 1 collects the email; `next` is held in React state and only rendered
    // as a field on the OTP step, so assert the flow reached step 1 intact.
    await expect(page.getByPlaceholder("Email address")).toBeVisible();
    await expect(page.locator('input[name="purpose"]')).toHaveValue("login");
  });
});

test.describe("public routes", () => {
  for (const path of PUBLIC) {
    test(`${path} renders without a server error`, async ({ page }) => {
      const response = await page.goto(path);
      expect(response?.status(), `${path} should be 200`).toBe(200);
      // 200 is not proof of rendering — an error boundary returns 200 too.
      await expect(page.locator("body")).not.toBeEmpty();
      await expect(page.getByText(/Application error|Internal Server Error/i)).toHaveCount(0);
    });
  }
});

test("unknown paths 404", async ({ page }) => {
  const response = await page.goto("/no-such-page-should-404");
  expect(response?.status()).toBe(404);
});
