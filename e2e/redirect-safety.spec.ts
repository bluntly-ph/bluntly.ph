import { expect, test } from "@playwright/test";

/**
 * `?next=` must never send someone off the site.
 *
 * `safeNext` tested `startsWith("/") && !startsWith("//")`, which looks right
 * and is not: browsers normalise backslashes to forward slashes per the URL
 * spec, so `/\evil.com` passed both checks and resolved to `https://evil.com/`.
 * `https://www.bluntly.ph/login?next=/\evil.com` was therefore a link that
 * delivered someone to an attacker's site immediately after a successful
 * sign-in — the most credible possible moment to show them a second login form.
 *
 * These run signed-out, so they check what a signed-out visitor can already
 * see: that a hostile `next` is not reflected into anything that would navigate
 * off-origin. The redirect itself happens in a server action after OTP, which
 * this suite cannot reach; `safeNext` is what makes that hop safe and its
 * behaviour is enumerated in the unit-level sense in the commit that fixed it.
 */

const HOSTILE = [
  "//evil.example",
  "/\\evil.example",
  "/\\/evil.example",
  "/..//evil.example",
  "https://evil.example",
  "javascript:alert(1)",
];

for (const next of HOSTILE) {
  test(`login page does not offer an off-site destination for ${next}`, async ({
    page,
  }) => {
    await page.goto(`/login?next=${encodeURIComponent(next)}`);

    const origin = new URL(page.url()).origin;

    // Anything that could navigate: links, form targets, and the hidden field
    // the form carries through the OTP round-trip.
    const destinations = await page.evaluate(() => {
      const out: string[] = [];
      document.querySelectorAll("a[href]").forEach((a) =>
        out.push((a as HTMLAnchorElement).href),
      );
      document.querySelectorAll("form[action]").forEach((f) =>
        out.push((f as HTMLFormElement).action),
      );
      return out;
    });

    const offsite = destinations.filter((d) => {
      try {
        return new URL(d).origin !== origin && !d.startsWith("mailto:");
      } catch {
        return false;
      }
    });

    expect(offsite, `hostile next=${next} produced off-site destinations`).toEqual(
      [],
    );
  });
}

test("a legitimate next survives the hop to signup", async ({ page }) => {
  /**
   * Only the first step is reachable signed-out. `next` is carried from here
   * as a React prop into `CodeStep`, which is where the hidden input lives, and
   * reaching that step means sending a real OTP — so what is checked here is
   * the hop that *is* observable: the "create an account" link must not drop
   * the destination, or someone who signs up instead of logging in lands on the
   * home page having lost where they were going.
   */
  await page.goto("/login?next=%2Freviews%2Fnew");

  const signupLink = page.locator('a[href*="/signup"]').first();
  await expect(signupLink).toHaveAttribute(
    "href",
    /next=%2Freviews%2Fnew/,
  );
});
