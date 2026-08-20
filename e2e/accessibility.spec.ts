import { test, expect } from "@playwright/test";

/**
 * Input-target size and heading structure.
 *
 * Both of these are the kind of defect that never shows up in a build, a
 * typecheck, or a visual glance — a 21px-tall link looks completely fine on a
 * desktop monitor with a mouse and is genuinely hard to hit on a phone. They
 * were found by measuring, so they are kept honest by measuring.
 *
 * The bar is WCAG 2.5.8 (AA): 24x24 CSS pixels minimum. The category rail was
 * built at 21px tall, which failed for every category on the primary browse
 * path. It is fixed by padding the hit area without moving the drawn design,
 * so a regression here means someone removed that padding.
 */

// Public pages only. The role-gated surfaces (/moderate, /dashboard,
// /contracts) are deliberately absent: this suite runs without credentials, and
// giving it a moderator session would make a read-only suite capable of writes.
//
// /moderate was checked by hand on 2026-08-20 and had two defects, both fixed:
// its card titles followed the page h1 with no h2 between them, and the
// proof-of-purchase control presented a ~14px hit area. Those are now covered
// by e2e/moderator-a11y.spec.ts, which is opt-in on E2E_MODERATOR_TOKEN and
// skips until the isolated test environment exists.
const PAGES = ["/", "/search", "/categories", "/requests", "/questions"] as const;

/** WCAG 2.5.8 AA. 44px is the AAA//platform guideline; 24 is the hard floor. */
const MIN_TARGET = 24;

test.describe("input target size", () => {
  for (const path of PAGES) {
    test(`${path} has no control smaller than ${MIN_TARGET}px`, async ({ page }) => {
      await page.goto(path);
      await expect(page.locator("body")).not.toBeEmpty();

      const undersized = await page.evaluate((min) => {
        const bad: string[] = [];
        document.querySelectorAll("a,button,[role=button]").forEach((el) => {
          const r = el.getBoundingClientRect();
          // Zero-size elements are not rendered; skip rather than fail on them.
          if (!r.width || !r.height) return;
          // An inline link inside a paragraph is exempt under 2.5.8 - the
          // target is the text itself and it flows with the sentence.
          if (el.closest("p")) return;
          if (Math.min(r.width, r.height) < min) {
            const label = (
              el.getAttribute("aria-label") ||
              el.textContent ||
              el.tagName
            )
              .trim()
              .slice(0, 40);
            bad.push(`${label} (${Math.round(r.width)}x${Math.round(r.height)})`);
          }
        });
        return bad;
      }, MIN_TARGET);

      expect(
        undersized,
        `${path} has ${undersized.length} control(s) under ${MIN_TARGET}px: ${undersized.join(", ")}`,
      ).toEqual([]);
    });
  }
});

test.describe("heading structure", () => {
  for (const path of PAGES) {
    test(`${path} does not skip a heading level`, async ({ page }) => {
      await page.goto(path);

      const levels = await page.evaluate(() =>
        [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((h) => ({
          level: Number(h.tagName[1]),
          text: (h.textContent ?? "").trim().slice(0, 40),
        })),
      );

      const skips = levels
        .map((h, i) =>
          i && h.level - levels[i - 1].level > 1
            ? `${levels[i - 1].level}->${h.level} at "${h.text}"`
            : null,
        )
        .filter(Boolean);

      expect(skips, `${path} skips heading levels: ${skips.join("; ")}`).toEqual([]);
    });
  }
});
