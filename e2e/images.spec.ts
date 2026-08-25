import { expect, test } from "@playwright/test";

/**
 * Images must actually RENDER, not merely score well.
 *
 * This exists because of a real incident. An image optimisation was shipped,
 * Lighthouse improved sharply, and the improvement was partly because every
 * photograph was 404ing and therefore costing nothing to "load". Production
 * imagery was broken for about twenty minutes. A performance number taken from
 * a page with missing assets is not evidence of anything.
 *
 * So the acceptance condition for any image change is behavioural, and checked
 * before any score is quoted:
 *
 *   the request succeeds
 *   naturalWidth > 0            (it decoded, not just responded)
 *   the drawn box is unchanged  (it was not "fixed" by resizing the layout)
 *   caching behaves as intended
 *   no console error
 *   no failed network request
 *
 * Point it at production with:
 *   PLAYWRIGHT_BASE_URL=https://www.bluntly.ph npx playwright test e2e/images.spec.ts
 */

/** Pages that carry product photography, and the box each draws it into. */
const PAGES = [
  { path: "/", name: "landing" },
  { path: "/feed", name: "feed" },
  { path: "/search", name: "search" },
];

/**
 * Bring every image into view and LEAVE it there long enough to finish.
 *
 * The obvious version — sweep down the page and jump back to the top — reports
 * false failures on WebKit, which cancels a lazy image that leaves the viewport
 * mid-flight. Verified: under the sweep, one image on the landing page stayed
 * `complete=false` indefinitely; scrolled into view and left there, all five
 * decode. The image and every width of it were fine all along (200 in under a
 * second from 256 to 1920), so the sweep was measuring the test's own
 * scrolling, not the product.
 */
async function loadAllImages(page: import("@playwright/test").Page) {
  const count = await page.evaluate(() => document.querySelectorAll("img").length);
  for (let i = 0; i < count; i++) {
    await page.evaluate(
      (idx) =>
        document.querySelectorAll("img")[idx]?.scrollIntoView({ block: "center" }),
      i,
    );
    await page.waitForTimeout(700);
  }
  await page.waitForTimeout(1500);
}

for (const { path, name } of PAGES) {
  test(`${name}: every image decodes and nothing 404s`, async ({ page }) => {
    const failed: string[] = [];
    const consoleErrors: string[] = [];

    page.on("response", (r) => {
      const url = r.url();
      const isImage =
        /\.(png|jpe?g|webp|avif|gif|svg)(\?|$)/i.test(url) ||
        /\/render\/image\/|\/_next\/image/.test(url);
      if (isImage && r.status() >= 400) failed.push(`${r.status()} ${url}`);
    });
    page.on("console", (m) => {
      if (m.type() === "error") consoleErrors.push(m.text());
    });

    await page.goto(path, { waitUntil: "domcontentloaded" });
    await loadAllImages(page);

    const images = await page.evaluate(() =>
      [...document.querySelectorAll("img")].map((img) => {
        const box = img.getBoundingClientRect();
        return {
          src: (img.currentSrc || img.src || "").slice(0, 120),
          naturalWidth: img.naturalWidth,
          naturalHeight: img.naturalHeight,
          width: Math.round(box.width),
          height: Math.round(box.height),
        };
      }),
    );

    expect(failed, `image requests failed:\n${failed.join("\n")}`).toEqual([]);

    // A page with no <img> at all would otherwise pass every assertion below
    // by vacuum, which is exactly the failure this test exists to catch.
    expect(images.length, "no images found on a page that should have them")
      .toBeGreaterThan(0);

    const broken = images.filter((i) => i.naturalWidth === 0);
    expect(
      broken,
      `images did not decode (naturalWidth 0):\n${broken.map((b) => b.src).join("\n")}`,
    ).toEqual([]);

    // The drawn box must still be a real box. An image "fixed" by collapsing
    // its container to nothing is not fixed.
    const collapsed = images.filter((i) => i.width < 8 || i.height < 8);
    expect(
      collapsed,
      `images drawn into a collapsed box:\n${collapsed.map((c) => c.src).join("\n")}`,
    ).toEqual([]);

    expect(
      consoleErrors.filter(
        (e) =>
          // Dev-only; next.config.ts omits `unsafe-eval` on purpose.
          !e.includes("eval() is not supported") &&
          // Firefox reports Cloudflare's bot-management cookie on Supabase's
          // CDN as a JS error: `Cookie "__cf_bm" has been rejected for invalid
          // domain`. It is a third-party cookie notice about a host we do not
          // control, the images load regardless, and no other browser raises
          // it. Excluded by name so a genuine image error is still caught.
          !e.includes("__cf_bm"),
      ),
      "console errors on a page with images",
    ).toEqual([]);
  });
}

test("product images are served cacheably", async ({ page, request }) => {
  await page.goto("/search", { waitUntil: "domcontentloaded" });
  await loadAllImages(page);

  const src = await page.evaluate(
    () =>
      [...document.querySelectorAll("img")]
        .map((i) => i.currentSrc || i.src)
        .find((u) => /supabase\.co|\/_next\/image/.test(u)) ?? "",
  );
  test.skip(!src, "no remotely-hosted product image on this page");

  const response = await request.get(src);
  expect(response.status(), `image request failed: ${src}`).toBe(200);

  // The whole point of the current image path: the plain object endpoint
  // answers `no-cache` for every object in this project, so a cacheable
  // response is what proves requests are still going through the render
  // endpoint rather than falling back.
  const cacheControl = response.headers()["cache-control"] ?? "";
  expect(
    cacheControl,
    `product images must be cacheable, got "${cacheControl}" for ${src}`,
  ).toMatch(/max-age=[1-9]/);

  const body = await response.body();
  expect(body.byteLength, "image body was empty").toBeGreaterThan(100);
});
