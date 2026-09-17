import { test, expect } from "@playwright/test";

/**
 * Link prefetches must not meet the proxy (proxy.ts, the matcher's `missing`).
 *
 * Measured on production 2026-09-17, signed out, desktop: /feed and /search
 * prefetched their visible gated links (Write a review, Profile, Ask a
 * question); the proxy answered each prefetch with a 307 to /login?next=…; the
 * router replayed the redirect and never closed the first response, so three
 * requests stayed open for the life of the page — Lighthouse timed out waiting
 * for the network to go quiet. The same proxy pass counted every prefetched
 * review link as a VIEW of that review.
 *
 * A signed-out page load, before anyone clicks anything, must therefore issue
 * no request for /login?next= (only a redirected prefetch produces one) and
 * leave no request hanging once the page has settled.
 *
 * READ-ONLY: GET navigations, nothing clicked.
 */

const PAGES = ["/feed", "/search", "/questions"];

test.describe("prefetch hygiene (signed out, desktop)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  for (const path of PAGES) {
    test(`${path}: no redirected prefetch and nothing left open`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "chromium", "request lifecycle observed in Chromium only");

      const open = new Map<string, string>();
      const loginRequests: string[] = [];
      page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.pathname === "/login" && url.searchParams.has("next")) loginRequests.push(url.pathname + url.search);
        open.set(`${request.method()} ${request.url()}#${open.size}`, request.url());
      });
      const settle = (request: import("@playwright/test").Request) => {
        for (const [key, url] of open) {
          if (url === request.url()) {
            open.delete(key);
            break;
          }
        }
      };
      page.on("requestfinished", settle);
      page.on("requestfailed", settle);

      await page.goto(path, { waitUntil: "load" });
      // Viewport prefetching happens after hydration; give it time to happen and finish.
      await page.waitForTimeout(6000);

      expect(loginRequests, `${path} prefetched a gated link and was redirected to /login`).toEqual([]);
      const pending = [...open.values()].filter((url) => !url.startsWith("data:"));
      expect(pending, `${path} left requests open after settling`).toEqual([]);
    });
  }
});
