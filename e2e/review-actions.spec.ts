import { expect, test } from "@playwright/test";

/**
 * Review-detail interactions filed by QA (BUG-014, BUG-015) plus the navigation
 * and 404 fixes (BUG-003, BUG-011).
 *
 * These are the checks a screenshot cannot make: a control that renders but does
 * nothing on click looks identical to a working one until you click it.
 */

const SHOWCASE_REVIEW = "00000000-0000-0000-0000-0000000e0001";

test.describe("BUG-015 — share is clickable", () => {
  test("clicking Share copies the link and says so", async ({ page, context, browserName }) => {
    // The clipboard needs permission in Chromium; Firefox/WebKit don't support
    // granting it, so there we only assert the control responds at all.
    if (browserName === "chromium") {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    }
    await page.goto(`/reviews/${SHOWCASE_REVIEW}`);

    const share = page.getByRole("button", { name: /share/i });
    await expect(share).toBeVisible();
    await share.click();

    // The label is the observable proof the handler ran — before the fix the
    // button had no onClick at all and nothing whatsoever happened.
    await expect(
      page.getByRole("button", { name: /link copied|copy failed/i }),
    ).toBeVisible({ timeout: 5000 });

    if (browserName === "chromium") {
      const copied = await page.evaluate(() => navigator.clipboard.readText());
      expect(copied).toContain(`/reviews/${SHOWCASE_REVIEW}`);
    }
  });
});

test.describe("BUG-014 — the comment surface exists", () => {
  test("a signed-out reader sees the thread and a way to join it", async ({ page }) => {
    await page.goto(`/reviews/${SHOWCASE_REVIEW}`);

    await expect(
      page.getByRole("heading", { name: /comments?$|^\d+ comments?$/i }),
    ).toBeVisible();
    // Signed out: read-only, with a login route that returns here afterwards.
    const join = page.getByRole("link", { name: /^log in$/i }).last();
    await expect(join).toBeVisible();
    await expect(join).toHaveAttribute(
      "href",
      `/login?next=/reviews/${SHOWCASE_REVIEW}`,
    );
    // No composer for a guest — posting is gated server-side too.
    await expect(page.getByRole("textbox", { name: /add a comment/i })).toHaveCount(0);
  });
});

test.describe("BUG-003 — styled 404", () => {
  test("an unknown path returns 404 with a route home", async ({ page }) => {
    const response = await page.goto("/this-page-does-not-exist");
    expect(response?.status()).toBe(404);

    // Not the bare framework error: brand chrome and two ways out.
    await expect(page.getByRole("link", { name: /back home/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /search reviews/i })).toBeVisible();
    await expect(page.locator("footer")).toBeVisible();
  });
});

test.describe("BUG-011 — categories round trip", () => {
  test("a filtered view can get back to /categories", async ({ page }) => {
    await page.goto("/categories");
    await page.getByRole("link", { name: /beauty/i }).first().click();
    await expect(page).toHaveURL(/\/search\?category=beauty&from=categories/);

    // The back link QA asked for.
    await expect(
      page.getByRole("link", { name: /all categories/i }),
    ).toBeVisible();

    // "All" returns to /categories rather than dead-ending on /search.
    await page.getByRole("link", { name: /^all$/i }).first().click();
    await expect(page).toHaveURL(/\/categories$/);
  });

  test("plain search still treats All as 'clear the filter'", async ({ page }) => {
    // The fix must not hijack /search reached any other way.
    await page.goto("/search?category=beauty");
    await expect(
      page.getByRole("link", { name: /all categories/i }),
    ).toHaveCount(0);
    await page.getByRole("link", { name: /^all$/i }).first().click();
    await expect(page).toHaveURL(/\/search$/);
  });
});

test.describe("BUG-005 — the footer stays put on an empty result set", () => {
  test("footer sits at or below the fold when a filter returns nothing", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    // A query that cannot match anything, so the results area collapses.
    await page.goto("/search?q=zzzzqqqqnothingmatchesthis");
    await expect(page.getByText(/no reviews found/i)).toBeVisible();

    const geometry = await page.evaluate(() => {
      const f = document.querySelector("footer")!.getBoundingClientRect();
      const main = document.querySelector("main")!.getBoundingClientRect();
      return {
        viewportH: window.innerHeight,
        docH: document.documentElement.scrollHeight,
        footerTop: f.top + window.scrollY,
        footerBottom: f.bottom + window.scrollY,
        mainBottom: main.bottom + window.scrollY,
      };
    });

    // The real property, measured rather than eyeballed: the footer ends at the
    // document's end (no dead band under it) and reaches at least the fold, so
    // it is anchored rather than floating mid-page.
    expect(geometry.docH - geometry.footerBottom).toBeLessThanOrEqual(1);
    expect(geometry.footerBottom).toBeGreaterThanOrEqual(geometry.viewportH - 1);

    // And the empty state now fills the space above it, so nothing is left but
    // the footer's own 16px top margin — not the tall blank band QA saw.
    expect(geometry.footerTop - geometry.mainBottom).toBeLessThanOrEqual(20);
  });
});
