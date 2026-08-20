import { expect, test, type Page } from "@playwright/test";

/**
 * Accessibility of the role-gated moderator surface.
 *
 * Kept out of `accessibility.spec.ts` because that suite runs with no
 * credentials by design — giving it a session would make a deliberately
 * read-only suite capable of writes. This file needs a moderator, so it is
 * opt-in and skips loudly rather than silently passing.
 *
 * It exists because walking /moderate by hand on 2026-08-20 found two defects
 * no automated suite could have caught: card titles followed the page h1 with
 * no h2 between them, and the proof-of-purchase control had a ~14px hit area.
 * Both are now fixed; this keeps them fixed.
 *
 * To run it:
 *   1. provision the isolated test environment (docs/ENVIRONMENTS.md)
 *   2. mint a moderator token against THAT environment:
 *        cd backend && .venv/Scripts/python -m scripts.mint_e2e_moderator
 *   3. E2E_MODERATOR_TOKEN=<token> npx playwright test e2e/moderator-a11y.spec.ts
 *
 * Never point this at production: it needs a moderator account, and creating
 * one there would mean promoting a real user or leaving a privileged fixture
 * behind.
 */

const TOKEN = process.env.E2E_MODERATOR_TOKEN;
const MIN_TARGET = 24; // WCAG 2.5.8 AA hard floor.

test.describe("moderator surface accessibility", () => {
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

  async function gotoModerate(page: Page) {
    const resp = await page.goto("/moderate");
    expect(page.url(), "the token must actually be a moderator's").toContain("/moderate");
    return resp;
  }

  test("headings descend without skipping a level", async ({ page }) => {
    await gotoModerate(page);
    const levels = await page.locator("h1,h2,h3,h4").evaluateAll(
      (hs) => hs.map((h) => Number(h.tagName[1])),
    );
    expect(levels.length, "the page should have headings").toBeGreaterThan(0);
    expect(levels[0], "the first heading is the page h1").toBe(1);
    for (let i = 1; i < levels.length; i += 1) {
      expect(
        levels[i] - levels[i - 1],
        `heading jumped h${levels[i - 1]} -> h${levels[i]} (sequence ${levels.join(">")})`,
      ).toBeLessThanOrEqual(1);
    }
  });

  test(`no control is smaller than ${MIN_TARGET}px`, async ({ page }) => {
    await gotoModerate(page);
    const undersized = await page.locator("a,button,input,select").evaluateAll(
      (els, min) => els
        .map((el) => {
          const r = el.getBoundingClientRect();
          return { r, label: (el.getAttribute("aria-label") || el.textContent || el.tagName).trim().slice(0, 40) };
        })
        // Zero-sized elements are hidden, not undersized.
        .filter(({ r }) => r.width > 0 && r.height > 0 && (r.width < min || r.height < min))
        .map(({ r, label }) => `${label} (${Math.round(r.width)}x${Math.round(r.height)})`),
      MIN_TARGET,
    );
    expect(undersized, "controls below the WCAG 2.5.8 floor").toEqual([]);
  });

  test("every control has an accessible name", async ({ page }) => {
    await gotoModerate(page);
    const unnamed = await page.locator("button,a").evaluateAll((els) => els
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        return !(el.getAttribute("aria-label") || el.textContent || "").trim()
          && !el.querySelector("img[alt]:not([alt=''])");
      })
      .map((el) => el.outerHTML.slice(0, 60)));
    expect(unnamed, "controls a screen reader cannot announce").toEqual([]);
  });

  test("the queue is reachable by keyboard", async ({ page }) => {
    await gotoModerate(page);
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? `${el.tagName}:${(el.textContent || "").trim().slice(0, 20)}` : null;
    });
    expect(focused, "Tab should move focus into the page").not.toBeNull();
    expect(focused).not.toMatch(/^BODY/);
  });

  test("does not scroll horizontally on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoModerate(page);
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(overflows, "the moderator queue overflows at 390px").toBe(false);
  });

  test("loads with no console errors or failed requests", async ({ page }) => {
    const problems: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") problems.push(m.text()); });
    page.on("pageerror", (e) => problems.push(String(e)));
    page.on("response", (r) => {
      if (r.status() >= 400) problems.push(`${r.status()} ${r.url()}`);
    });
    await gotoModerate(page);
    await page.waitForLoadState("networkidle");
    expect(problems).toEqual([]);
  });
});
