import { test, expect, type Page } from "@playwright/test";

/**
 * The site's own Back control (BUG-033).
 *
 * QA: "Go to Search, open a trending review, press the site's back button — it
 * returns to Home instead of Search." It did, because the control was a
 * `<Link href="/">`. The browser's own back button was fine the whole time,
 * which is exactly why this needs a browser test: a unit test of the component
 * cannot see where a click actually lands.
 *
 * Two behaviours, and both matter:
 *
 *   with history    — back goes where the reader came from, with their place
 *   without history — a review opened cold (a shared link, a new tab) still has
 *                     a Back that goes somewhere real, not nowhere
 *
 * The control lives in the phone bar (`md:hidden`), so these run at a phone
 * width regardless of the project's device.
 *
 * READ-ONLY. Every request here is a GET against public pages, so it is safe to
 * point at production; nothing is created.
 */

test.use({ viewport: { width: 390, height: 844 } });

/**
 * The first REVIEW a search results page links to.
 *
 * Not simply `a[href^="/reviews/"]`: the page also links `/reviews/new`, the
 * composer, which is guarded and would bounce to sign-in — a different page for
 * a different reason, and a test that passed or failed on it would be testing
 * the wrong thing.
 */
async function firstReviewHref(page: Page): Promise<string> {
  const link = page.locator('a[href^="/reviews/"]:not([href="/reviews/new"])').first();
  await expect(link, "the search page links no review to open").toBeVisible();
  const href = await link.getAttribute("href");
  expect(href).toBeTruthy();
  return href as string;
}

test("Search → review → the site's Back returns to Search, not Home", async ({ page }) => {
  await page.goto("/search");
  const href = await firstReviewHref(page);

  // A real in-app navigation, so there is history to go back through — the
  // thing a direct `page.goto(review)` would not create.
  await page.locator(`a[href="${href}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));

  const back = page.getByRole("button", { name: "Back" });
  await expect(back, "with history, Back is a history button, not a link").toBeVisible();
  await back.click();

  await expect(page).toHaveURL(/\/search(\?|$)/);
  await expect(page).not.toHaveURL(/^[^?]*\/$/);
});

test("Search keeps its query when the site's Back returns to it", async ({ page }) => {
  // The complaint was losing the reader's place, not just the page. A query is
  // the most obvious part of that place.
  await page.goto("/search?q=a");
  const href = await firstReviewHref(page);
  await page.locator(`a[href="${href}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));

  await page.getByRole("button", { name: "Back" }).click();
  await expect(page).toHaveURL(/\/search\?q=a/);
});

test("a review opened directly still has a Back that goes somewhere real", async ({
  context,
}) => {
  // Find a review id without creating history in the page under test.
  const probe = await context.newPage();
  await probe.goto("/search");
  const href = await firstReviewHref(probe);
  await probe.close();

  const fresh = await context.newPage();
  await fresh.goto(href);
  // Hydration is the moment the first implementation went wrong: the server
  // rendered the link, then `history.length > 1` — true in a fresh tab, which
  // counts its blank starting entry — swapped it for a history button that would
  // have taken the reader OFF the site. Wait it out before asserting.
  await fresh.waitForLoadState("networkidle");

  const back = fresh.getByRole("link", { name: "Back" });
  await expect(back, "after hydration Back must still be the fallback link").toBeVisible();
  await expect(back).toHaveAttribute("href", "/");
  await expect(fresh.getByRole("button", { name: "Back" })).toHaveCount(0);

  await back.click();
  await expect(fresh).toHaveURL(/\/$/);
  await fresh.close();
});

test("once back at the entry page, the next Back does not leave the site", async ({ page }) => {
  // Search (entry) → review → Back → Search. Search has no Back control, so
  // re-enter a review and confirm Back is a history button again — the count
  // went down on the back and up on the new navigation, and never past what
  // this tab actually visited.
  await page.goto("/search");
  const href = await firstReviewHref(page);
  await page.locator(`a[href="${href}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page).toHaveURL(/\/search(\?|$)/);

  await page.locator(`a[href="${href}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page).toHaveURL(/\/search(\?|$)/);
});

test("the store page's Back falls back to seller search when opened cold", async ({ page }) => {
  // The QA seller (docs/QA_HANDOFF.md) is a real, labelled row in production,
  // so this needs no fixture and creates nothing.
  await page.goto("/sellers/5e11e700-0000-4000-8000-000000000999");

  const back = page.getByRole("link", { name: "Back" });
  await expect(back).toBeVisible();
  await expect(back).toHaveAttribute("href", "/search?tab=sellers");
});
