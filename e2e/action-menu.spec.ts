import { test, expect, type Page } from "@playwright/test";

/**
 * The mobile action menu, as "Action Menu.png" draws it and as the owner asked
 * for on 2026-09-14: mounted on the discovery surfaces so QA can start each of
 * the three workflows from a phone.
 *
 * Geometry is asserted against the frame (390x844): a 60x60 FAB 32px from the
 * right and bottom edges, hidden from 768px up because no reference places it
 * on tablet or desktop.
 *
 * Signed out only. All three destinations sit behind the email-OTP login, which
 * cannot be driven here, so each action is proven to reach its REAL route's
 * guard with the return path intact. Signed in, the same link lands on the
 * workflow itself; that half needs a session and is checked by hand.
 *
 * Covers the surfaces that render without data. The review and seller pages
 * also mount the menu but need a record to exist.
 */

const MOBILE = { width: 390, height: 844 };
// Where the Figma file draws the FAB. The store page carries it too, but needs a
// seller record to render; the routes below must NOT show it.
const SURFACES = ["/search"] as const;
const NO_FAB = ["/", "/feed", "/categories", "/questions"] as const;
const ACTIONS = [
  { name: "Ask a Question", path: "/questions/new" },
  { name: "Rate a Seller", path: "/sellers/rate" },
  { name: "Write a Review", path: "/reviews/new" },
] as const;

test.use({ viewport: MOBILE });

const fab = (page: Page) => page.getByRole("button", { name: "Actions", exact: true });
const panel = (page: Page) => page.locator("[data-action-menu-panel]");

async function openMenu(page: Page, path = "/search") {
  await page.goto(path);
  await fab(page).click();
  await expect(fab(page)).toHaveAttribute("aria-expanded", "true");
  await expect(panel(page)).toBeVisible();
}

test.describe("mobile action menu", () => {
  for (const path of SURFACES) {
    test(`the FAB sits 32px from the right and bottom edges on ${path}`, async ({ page }) => {
      await page.goto(path);
      const button = fab(page);
      await expect(button).toBeVisible();
      await expect(button).toHaveAttribute("aria-expanded", "false");
      const box = await button.boundingBox();
      expect(box).not.toBeNull();
      expect(Math.round(box!.width)).toBe(60);
      expect(Math.round(box!.height)).toBe(60);
      expect(Math.round(MOBILE.width - (box!.x + box!.width))).toBe(32);
      expect(Math.round(MOBILE.height - (box!.y + box!.height))).toBe(32);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }

  test("expanding shows the three actions in the drawn order over a 25% scrim", async ({ page }) => {
    await openMenu(page);
    const links = panel(page).getByRole("link");
    await expect(links).toHaveText(ACTIONS.map((a) => a.name));
    await expect(fab(page)).toHaveAttribute("aria-controls", /.+/);
    const scrim = page.locator("[data-action-menu-scrim]");
    await expect(scrim).toBeVisible();
    await expect(scrim).toHaveCSS("background-color", "rgba(0, 0, 0, 0.25)");
  });

  test("Escape closes the menu and returns focus to the FAB", async ({ page }) => {
    await openMenu(page);
    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveCount(0);
    await expect(fab(page)).toBeFocused();
    await expect(fab(page)).toHaveAttribute("aria-expanded", "false");
  });

  test("tapping the scrim closes the menu without touching the page beneath", async ({ page }) => {
    await openMenu(page);
    const before = page.url();
    await page.mouse.click(40, 200);
    await expect(panel(page)).toHaveCount(0);
    expect(page.url()).toBe(before);
  });

  test("the close button closes the menu", async ({ page }) => {
    await openMenu(page);
    await page.getByRole("button", { name: "Close actions" }).click();
    await expect(panel(page)).toHaveCount(0);
  });

  for (const action of ACTIONS) {
    test(`${action.name} opens its real route, behind sign-in, keeping the return path`, async ({
      page,
    }) => {
      await openMenu(page);
      await panel(page).getByRole("link", { name: action.name }).click();
      await expect(page).toHaveURL(
        new RegExp(`/login\\?next=${encodeURIComponent(action.path)}(&|$)`),
      );
    });
  }

  for (const path of NO_FAB) {
    test(`no FAB on ${path}, which the Figma file does not draw it on`, async ({ page }) => {
      await page.goto(path);
      await expect(fab(page)).toHaveCount(0);
    });
  }

  for (const width of [768, 1440]) {
    test(`no FAB at ${width}px, where no reference places one`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/search");
      await expect(fab(page)).toBeHidden();
    });
  }
});
