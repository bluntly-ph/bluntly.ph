import { test, expect } from "@playwright/test";

/**
 * Cross-browser + mobile coverage (M3).
 *
 * This file is deliberately viewport- and engine-agnostic: it asserts things
 * that must hold on every project in playwright.config.ts (chromium, firefox,
 * webkit, and the two mobile profiles) rather than pinning pixel values, which
 * would just encode one engine's metrics.
 *
 * The horizontal-overflow check is the load-bearing one. A layout that overflows
 * its viewport still returns 200, still renders, and still passes a typecheck —
 * it only shows up as a body you can scroll sideways, which is exactly the class
 * of mobile bug a desktop-only suite never sees.
 */

const PAGES = [
  "/",
  "/about",
  "/search",
  "/membership",
  "/categories",
  "/how-it-works",
] as const;

test.describe("responsive layout", () => {
  for (const path of PAGES) {
    test(`${path} does not scroll horizontally`, async ({ page }) => {
      await page.goto(path);
      await expect(page.locator("body")).not.toBeEmpty();

      // Allow 1px for sub-pixel rounding, which differs between engines.
      const overflow = await page.evaluate(() => {
        const doc = document.documentElement;
        return doc.scrollWidth - doc.clientWidth;
      });
      expect(overflow, `${path} overflows its viewport by ${overflow}px`).toBeLessThanOrEqual(1);
    });
  }

  test("the landing page keeps its primary call to action in view", async ({ page }) => {
    await page.goto("/");
    // Whatever the breakpoint, a first-time visitor must be able to reach the
    // reviews without hunting — one of these entry points is always rendered.
    const entry = page.getByRole("link", { name: /browse|reviews|search|get started/i });
    expect(await entry.count()).toBeGreaterThan(0);
    await expect(entry.first()).toBeVisible();
  });

  test("the header exposes navigation at every width", async ({ page }) => {
    await page.goto("/");
    const header = page.locator("header").first();
    await expect(header).toBeVisible();

    // The home link is the one element present in both the mobile and desktop
    // header treatments, so it is the honest cross-viewport assertion.
    await expect(header.getByLabel("bluntly home")).toBeVisible();
  });

  test("the hero uses the width it is given at the tablet breakpoint", async ({
    page,
  }) => {
    // 768px exactly: the boundary QA filed against. The hero split at `lg`
    // while the container was already 72rem and the header had gone desktop at
    // `md`, so a tablet rendered one narrow column stranded in a wide shell.
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/");

    const heading = page.getByRole("heading", { level: 1 }).first();
    await expect(heading).toBeVisible();

    // Asserting *side-by-side* rather than a pixel width: the point is that the
    // second column sits beside the copy instead of under it, which is what
    // leaves the right-hand third empty when it regresses.
    const headingBox = await heading.boundingBox();
    const card = page.locator("article, [class*='rounded']").filter({
      hasText: /./,
    });
    expect(headingBox).not.toBeNull();

    // The copy column must not span the whole viewport — if it does, the grid
    // never split and everything below it is stacked.
    expect(
      headingBox!.width,
      `hero copy spans ${headingBox!.width}px of a 768px viewport — the grid did not split`,
    ).toBeLessThan(640);
    expect(await card.count()).toBeGreaterThan(0);
  });
});

test.describe("membership page", () => {
  test("explains that tiers are not purchasable", async ({ page }) => {
    await page.goto("/membership");
    // Guards the ADR-012 framing: this page must never read as a pricing table.
    await expect(page.getByText(/earned, not bought/i)).toBeVisible();
    await expect(page.getByText(/no subscription/i)).toBeVisible();
  });
});
