import { expect, test, type Page } from "@playwright/test";

/**
 * The admin console's architecture: separate screens, a shell that does not
 * document-scroll, and a rail that stays put.
 *
 * This exists because of a specific, non-obvious regression. Tailwind's
 * `sr-only` is `position: absolute`, so a visually-hidden heading with no
 * positioned ancestor resolves its containing block to the DOCUMENT — it
 * escapes an ancestor's `overflow: hidden` entirely while still contributing to
 * `scrollHeight`. One such heading on the Overview put the whole console into a
 * 379px document scroll at 1024px and dragged the sidebar off the top with it.
 * At 1440 it happened to land inside the viewport, so the bug was invisible in
 * a casual look and in every wider screenshot.
 *
 * `document.scrollHeight` alone is not a sufficient assertion: it can report a
 * gap on a page that does not actually scroll. These tests scroll the window
 * and check `scrollY`, which is what a moderator would experience.
 *
 * Same setup as moderator-a11y.spec.ts:
 *   E2E_MODERATOR_TOKEN=<token> npx playwright test e2e/admin-console.spec.ts
 *
 * Never point this at production.
 */

const TOKEN = process.env.E2E_MODERATOR_TOKEN;

const SCREENS = [
  "/moderate",
  "/moderate/review-queue",
  "/moderate/products",
  "/moderate/reviewers",
  "/moderate/affiliate-links",
  "/moderate/honesty-fund",
  "/moderate/analytics",
  "/moderate/activity",
];

const DESKTOP = [1440, 1280, 1024];

test.describe("admin console shell", () => {
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

  async function settle(page: Page, route: string) {
    await page.goto(route);
    await page.waitForTimeout(800);
  }

  for (const width of DESKTOP) {
    test(`the document never scrolls at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 860 });
      for (const route of SCREENS) {
        await settle(page, route);
        const scrolled = await page.evaluate(() => {
          window.scrollTo(0, 5000);
          const y = window.scrollY;
          window.scrollTo(0, 0);
          return y;
        });
        expect(scrolled, `${route} must not scroll the document`).toBe(0);
      }
    });

    test(`the rail does not move when the workspace scrolls at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 860 });
      for (const route of SCREENS) {
        await settle(page, route);
        const moved = await page.evaluate(() => {
          const rail = document.querySelector("aside");
          const main = document.querySelector("main");
          if (!rail || !main) return null;
          const before = rail.getBoundingClientRect().top;
          main.scrollTop = main.scrollHeight;
          const after = rail.getBoundingClientRect().top;
          main.scrollTop = 0;
          return Math.abs(after - before);
        });
        expect(moved, `${route} rail must be stationary`).toBeLessThanOrEqual(1);
      }
    });
  }

  test("a visually-hidden heading cannot extend the page", async ({ page }) => {
    // The regression, pinned directly: every sr-only element must be clipped by
    // an ancestor rather than resolving its containing block to the document.
    await page.setViewportSize({ width: 1024, height: 860 });
    await settle(page, "/moderate");
    const escaped = await page.evaluate(() => {
      const out: string[] = [];
      for (const el of document.querySelectorAll(".sr-only")) {
        if (getComputedStyle(el).position !== "absolute") continue;
        let anc = el.parentElement;
        let contained = false;
        while (anc && anc !== document.body) {
          const cs = getComputedStyle(anc);
          if (cs.position !== "static") { contained = true; break; }
          anc = anc.parentElement;
        }
        if (!contained) out.push(el.textContent?.trim().slice(0, 40) ?? "(empty)");
      }
      return out;
    });
    expect(escaped, "sr-only elements need a positioned ancestor or they extend the document").toEqual([]);
  });

  test("Overview and Review Queue are separate screens", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 860 });

    await settle(page, "/moderate");
    await expect(
      page.locator('nav[aria-label="Queue pages"]'),
      "the Overview must not embed the queue workbench",
    ).toHaveCount(0);
    await expect(page.locator("#admin-kpis")).toBeVisible();

    await settle(page, "/moderate/review-queue");
    await expect(
      page.locator('nav[aria-label="Queue pages"]'),
      "the Review Queue owns the table and its pagination",
    ).toBeVisible();
  });

  test("every navigation destination resolves", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 860 });
    await settle(page, "/moderate");
    const hrefs = await page.locator("aside nav a").evaluateAll(
      (as) => as.map((a) => a.getAttribute("href") ?? ""),
    );
    expect(hrefs.length, "the rail should have links").toBeGreaterThan(0);
    for (const href of hrefs) {
      expect(href, "no anchor-only or placeholder destinations").not.toMatch(/^#|javascript:/);
      const resp = await page.goto(href);
      expect(resp?.status(), `${href} must resolve`).toBe(200);
    }
  });

  test("unavailable sections are disabled, not silently clickable", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 860 });
    await settle(page, "/moderate");
    for (const label of ["Sellers", "Settings"]) {
      const item = page.locator(`aside [aria-disabled="true"]`, { hasText: label });
      await expect(item, `${label} must be marked unavailable`).toHaveCount(1);
      // Not a link, so it cannot be followed or focused as one.
      await expect(item.locator("a")).toHaveCount(0);
    }
  });
});
