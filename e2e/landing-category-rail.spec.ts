import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * The landing page's category rail ("What people are reading") scrolls sideways
 * and never vertically.
 *
 * On production (2026-09-17) the rail's wrapper was `overflow-x: auto`, which
 * makes overflow-y compute to auto as well, and each tab's 44px touch target
 * spilled 12px below the 20px row: scrollHeight 32 over clientHeight 20 at
 * every width. A vertical wheel or trackpad gesture over the rail moved only
 * the rail, and its icons were clipped. Read-only; safe against production.
 */

const RAIL = "section:has(h2:text-is('What people are reading')) ul";

function rail(page: Page): Locator {
  return page.locator(RAIL).first().locator("xpath=..");
}

async function assertNoVerticalRail(page: Page) {
  const scroller = rail(page);
  await expect(scroller).toBeVisible();

  const start = await scroller.evaluate((el) => ({
    top: el.scrollTop,
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight,
  }));
  expect(start.top).toBe(0);
  expect(start.scrollHeight, "the rail has vertical overflow to scroll").toBeLessThanOrEqual(
    start.clientHeight,
  );

  const box = await scroller.boundingBox();
  if (!box) throw new Error("rail has no box");
  await page.mouse.move(box.x + Math.min(60, box.width / 2), box.y + box.height / 2);
  await page.mouse.wheel(0, 240);
  await page.waitForTimeout(250);
  // A script or a focus change must not be able to move it either.
  const after = await scroller.evaluate((el) => {
    el.scrollTop = 50;
    return el.scrollTop;
  });
  expect(after, "the rail scrolled vertically").toBe(0);

  const clipped = await scroller.evaluate((el) => {
    const r = el.getBoundingClientRect();
    return [...el.querySelectorAll("li a")]
      .filter((a) => {
        const ar = a.getBoundingClientRect();
        if (ar.right < r.left || ar.left > r.right) return false; // scrolled off sideways
        return [a.querySelector("svg"), a].some((node) => {
          const nr = (node as Element).getBoundingClientRect();
          return nr.top < r.top - 0.5 || nr.bottom > r.bottom + 0.5;
        });
      })
      .map((a) => a.textContent?.trim());
  });
  expect(clipped, "category tabs clipped vertically").toEqual([]);

  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    "the page scrolls sideways",
  ).toBe(false);
}

test.describe("landing category rail", () => {
  for (const width of [1490, 1440]) {
    test(`does not scroll or clip vertically at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await assertNoVerticalRail(page);
    });
  }

  for (const width of [768, 390]) {
    test(`still scrolls sideways, never vertically, at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/");
      await assertNoVerticalRail(page);

      const scroller = rail(page);
      const moved = await scroller.evaluate((el) => {
        if (el.scrollWidth <= el.clientWidth) return null;
        el.scrollLeft = 120;
        return el.scrollLeft;
      });
      if (moved !== null) expect(moved, "the rail no longer scrolls sideways").toBeGreaterThan(0);
    });
  }
});
