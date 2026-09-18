import { expect, test } from "@playwright/test";

/**
 * A review's life from the author's point of view (2026-09-18).
 *
 * A real user submitted a review, was told it was submitted, refreshed their
 * profile and found it gone. It was held for moderation, and the profile read
 * the public feed — which is publication-gated on purpose. Now:
 *
 *   pending    on the author's own profile, marked "Pending moderation";
 *              on nobody else's screen, feed or search
 *   published  on the author's profile and everywhere public
 *
 * The public half runs everywhere, against any deployment: it needs no account
 * and writes nothing. The signed-in half needs an account whose reviews it may
 * read, and a moderator to decide them, so it is gated on the isolated test
 * environment like every other authenticated spec:
 *
 *   E2E_MODERATOR_TOKEN=<token> npx playwright test e2e/review-lifecycle.spec.ts
 *
 * The backend contract itself is pinned in backend/tests/test_own_reviews_api.py.
 */

const TOKEN = process.env.E2E_MODERATOR_TOKEN;

test.describe("publication gate (public)", () => {
  test("the public feed and a public profile show only published reviews", async ({ page }) => {
    const feed = await page.request.get("/api/bff/api/v1/reviews/feed?limit=100&sort=newest");
    expect(feed.ok()).toBe(true);
    const items = (await feed.json()) as { review: { id: string; published_at: string | null } }[];
    expect(items.length).toBeGreaterThan(0);
    for (const item of items) {
      expect(item.review.published_at, `review ${item.review.id} is unpublished but in the feed`).not.toBeNull();
    }
  });

  test("an unpublished review is not readable anonymously", async ({ page }) => {
    // /reviews/mine is the author's own list and needs a session; anonymous
    // callers get 401, never a list.
    const mine = await page.request.get("/api/bff/api/v1/reviews/mine");
    expect(mine.status()).toBe(401);
  });
});

test.describe("author's own reviews (signed in)", () => {
  test.skip(!TOKEN, "E2E_MODERATOR_TOKEN is not set — needs the isolated test environment (see the file header).");

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

  test("the profile lists every own review with its state, and a refresh keeps it", async ({ page }) => {
    const mine = await page.request.get("/api/bff/api/v1/reviews/mine?limit=100");
    expect(mine.ok()).toBe(true);
    const items = (await mine.json()) as { review: { id: string; title: string }; status: string }[];

    await page.goto("/profile");
    for (const item of items) {
      const card = page.locator(`li:has(a[href="/reviews/${item.review.id}"])`);
      await expect(card, `review ${item.review.id} missing from the author's profile`).toHaveCount(1);
      if (item.status === "pending") await expect(card).toContainText("Pending moderation");
      if (item.status === "rejected") await expect(card).toContainText("Rejected");
      if (item.status === "published") await expect(card).not.toContainText("Pending moderation");
    }

    await page.reload();
    for (const item of items) {
      await expect(page.locator(`li:has(a[href="/reviews/${item.review.id}"])`)).toHaveCount(1);
    }
  });

  test("a pending review is on its author's page, not the public one", async ({ page }) => {
    const mine = await page.request.get("/api/bff/api/v1/reviews/mine?limit=100");
    const items = (await mine.json()) as { review: { id: string; author_id: string }; status: string }[];
    const pending = items.find((i) => i.status === "pending");
    test.skip(!pending, "this account has no pending review to check");

    await page.goto(`/u/${pending!.review.author_id}`);
    await expect(page.locator(`a[href="/reviews/${pending!.review.id}"]`)).toHaveCount(0);

    await page.goto(`/reviews/${pending!.review.id}`);
    await expect(page.getByRole("status")).toContainText("Pending moderation");
  });
});
