import { expect, test } from "@playwright/test";

/**
 * `/feed` and the `/reviews/[id]` desktop layout.
 *
 * Read-only throughout, so this is safe against a deployed origin as well as a
 * local stack. Everything asserted here is the signed-out surface: the OTP
 * login cannot be driven end-to-end without a mail hook, so the authenticated
 * ranking is covered by the backend's pure-function tests
 * (`backend/tests/test_feed_ranking.py`) rather than pretended at here.
 */

const REVIEW = "/reviews/00000000-0000-0000-0000-0000000e0002";

test.describe("/feed — browsing surface", () => {
  test("renders reviews without an account", async ({ page }) => {
    await page.goto("/feed");

    // Discovery must not require signing in. If this ever redirects to /login,
    // the feed has stopped being a discovery surface.
    await expect(page).toHaveURL(/\/feed$/);
    await expect(page.getByRole("heading", { name: "For you", level: 1 })).toBeVisible();
    expect(await page.locator("article").count()).toBeGreaterThan(0);
  });

  test("a card carries enough to judge the review without opening it", async ({ page }) => {
    await page.goto("/feed");
    const card = page.locator("article").first();

    await expect(card.getByRole("heading")).toBeVisible();
    // The verdict is the platform's central claim; a feed row without it is
    // just a headline.
    await expect(
      card.getByText(/Yes, absolutely|It depends|Hard pass/),
    ).toBeVisible();
    await expect(card.getByLabel(/out of 5 stars/)).toBeVisible();
  });

  test("both tabs work and say which one is showing", async ({ page }) => {
    await page.goto("/feed");
    await expect(page.getByRole("tab", { name: "For you" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByRole("tab", { name: "Recent" }).click();
    await expect(page).toHaveURL(/tab=recent/);
    await expect(
      page.getByRole("heading", { name: "Recent reviews", level: 1 }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Recent" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("a card opens the full review", async ({ page }) => {
    await page.goto("/feed");
    const first = page.locator("article a").first();
    const href = await first.getAttribute("href");
    expect(href).toMatch(/^\/reviews\//);

    await first.click();
    await expect(page).toHaveURL(new RegExp(href!.replace(/\//g, "\\/")));
    await expect(page.locator("h1")).toBeVisible();
  });

  test("pagination is bounded and reversible", async ({ page }) => {
    // Page 2 may legitimately be empty on a small corpus; what must hold is
    // that it renders a page rather than an error, and offers the way back.
    await page.goto("/feed?page=2");
    await expect(page.locator("h1")).toBeVisible();
    const back = page.getByRole("link", { name: /Newer/ });
    if (await back.count()) {
      await back.first().click();
      await expect(page).toHaveURL(/\/feed$/);
    }
  });

  test("an absurd page number does not break the page", async ({ page }) => {
    const response = await page.goto("/feed?page=99999");
    expect(response?.status()).toBeLessThan(400);
    await expect(page.locator("h1")).toBeVisible();
  });

  test("desktop shows both rails, mobile shows neither", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/feed");
    await expect(page.locator('nav[aria-label="Browse"]')).toBeVisible();
    await expect(page.locator("aside")).toBeVisible();

    // Rails must disappear on a phone, not shrink onto it.
    await page.setViewportSize({ width: 393, height: 850 });
    await page.goto("/feed");
    await expect(page.locator('nav[aria-label="Browse"]')).toBeHidden();
    await expect(page.locator("aside")).toBeHidden();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      ),
    ).toBe(false);
  });

  test("the header offers Feed as a destination", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/");
    await page.getByRole("link", { name: "Feed", exact: true }).first().click();
    await expect(page).toHaveURL(/\/feed$/);
  });

  test("the landing page is still the landing page", async ({ page }) => {
    // `/` must not redirect to `/feed`; the marketing route is intact.
    const response = await page.goto("/");
    expect(response?.status()).toBeLessThan(400);
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("/reviews/[id] — desktop structure", () => {
  test("desktop gets the site header and a context sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(REVIEW);

    // The regression this guards: the page used to carry the phone's orange
    // back-bar at every width, so desktop had no wordmark, no search and no
    // navigation — an enlarged mobile layout.
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator('nav[aria-label="Review"]')).toBeHidden();
    await expect(page.locator("aside")).toBeVisible();
  });

  test("the reading column stays readable rather than spanning the window", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(REVIEW);
    const width = await page
      .locator("article")
      .first()
      .evaluate((el) => el.getBoundingClientRect().width);
    expect(width).toBeGreaterThan(500);
    expect(width).toBeLessThan(800);
  });

  test("tablet keeps the site header but drops the sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto(REVIEW);
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator('nav[aria-label="Review"]')).toBeHidden();
    await expect(page.locator("aside")).toBeHidden();
  });

  test("mobile keeps the phone bar and stacks", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 850 });
    await page.goto(REVIEW);
    await expect(page.locator('nav[aria-label="Review"]')).toBeVisible();
    await expect(page.locator("aside")).toBeHidden();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      ),
    ).toBe(false);
  });

  test("no width scrolls sideways", async ({ page }) => {
    for (const width of [1440, 1280, 1024, 768, 393]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(REVIEW);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        ),
        `horizontal scroll at ${width}px`,
      ).toBe(false);
    }
  });
});
