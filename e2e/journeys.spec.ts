import { expect, test } from "@playwright/test";

/**
 * The journeys a signed-out reader can take, end to end.
 *
 * The rest of the graph — the composers, the account menu, the moderator
 * queues — needs a session, and this project's login is an emailed one-time
 * code with no mail hook, so those are driven locally against fixture data by
 * `scripts/journey-check.mjs` instead. What is left here is what CI can prove
 * on every push: a result opens, a tab keeps the query, a filter reaches the
 * URL, a guard keeps the return path, and the footer's promises resolve.
 *
 * Read-only: nothing here submits anything.
 */

test.describe("public journeys", () => {
  test("a search result opens its review, and Back returns to the results", async ({ page }) => {
    await page.goto("/search");
    const card = page.locator("a[href^='/reviews/']:not([href='/reviews/new'])").first();
    const href = await card.getAttribute("href");
    test.skip(!href, "no published review in this environment");
    await card.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.locator("h1").first()).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/search/);
  });

  test("the query survives a change of tab", async ({ page }) => {
    await page.goto("/search?q=fan");
    await page.getByRole("link", { name: "Questions", exact: true }).click();
    await expect(page).toHaveURL(/tab=questions/);
    await expect(page).toHaveURL(/q=fan/);
    await page.getByRole("link", { name: "Sellers", exact: true }).click();
    await expect(page).toHaveURL(/tab=sellers/);
    await expect(page).toHaveURL(/q=fan/);
  });

  test("a category filter reaches the URL", async ({ page, viewport }) => {
    await page.goto("/search");
    if ((viewport?.width ?? 0) >= 1024) {
      // The website carries the categories in the rail beside the results.
      await page.getByRole("link", { name: "Gaming", exact: true }).click();
    } else {
      await page.getByRole("button", { name: "All filters" }).click();
      const sheet = page.getByRole("dialog", { name: "All filters" });
      await expect(sheet).toBeVisible();
      // The radio is sr-only behind its drawn ring, so the row is what is clicked.
      await sheet.getByText("Gaming", { exact: true }).click();
      await sheet.getByRole("button", { name: /Filter Reviews/i }).click();
    }
    await expect(page).toHaveURL(/category=gaming/);
  });

  test("a guarded route keeps the way back through login", async ({ page }) => {
    await page.goto("/reviews/new");
    await expect(page).toHaveURL(/\/login/);
    expect(new URL(page.url()).searchParams.get("next")).toBe("/reviews/new");
    await expect(page.getByPlaceholder("Email address")).toBeVisible();
  });

  test("the store dashboard keeps the way back too", async ({ page }) => {
    await page.goto("/sellers/any-store/dashboard");
    await expect(page).toHaveURL(/\/login/);
    expect(new URL(page.url()).searchParams.get("next")).toBe("/sellers/any-store/dashboard");
  });

  test("a question row opens its question", async ({ page }) => {
    await page.goto("/questions");
    const row = page.locator("a[href^='/questions/']:not([href='/questions/new'])").first();
    const href = await row.getAttribute("href");
    test.skip(!href, "no question in this environment");
    await row.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("the footer's policies resolve", async ({ page, request }) => {
    await page.goto("/about");
    for (const name of ["Privacy Policy", "Terms & Conditions", "Community Guidelines"]) {
      const href = await page.getByRole("link", { name, exact: true }).first().getAttribute("href");
      expect(href, `${name} has a destination`).toBeTruthy();
      const res = await request.get(href!);
      expect(res.status(), `${name} resolves`).toBe(200);
    }
  });
});
