import { chromium } from "playwright";

/**
 * Capture a legitimate authenticated session, once, with a human at the keyboard.
 *
 * This opens a REAL browser window against production and drives it only as far
 * as the login form. The OTP is typed by the account holder into that window —
 * nothing here reads a code, mints a token, injects a cookie, or touches a
 * guard. When the app navigates away from /login the session is saved so later
 * headless runs can reuse it instead of logging in again.
 *
 * The saved state is a live credential. It is written outside the repository,
 * to the session scratchpad, and never committed.
 */

const STATE = process.argv[2];
const EMAIL = "bluntly.ph@gmail.com";
const BASE = "https://www.bluntly.ph";

const browser = await chromium.launch({ headless: false, args: ["--window-size=1440,980"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(1500);

// Fill the email if the field is there; otherwise leave the page for the human.
try {
  await page.locator('input[type="email"]').first().fill(EMAIL, { timeout: 8000 });
  console.log(`  filled ${EMAIL}`);
  // Actually request the code. Filling the field alone sends nothing, which is
  // why the first two attempts sat waiting for a code that was never issued.
  await page.getByRole("button", { name: /send code/i }).click({ timeout: 8000 });
  console.log("  clicked Send code — check your inbox");
  await page.waitForTimeout(2000);
  const onCodeStep = await page.evaluate(() =>
    /code/i.test(document.body.innerText) &&
    document.querySelectorAll('input:not([type="hidden"])').length > 0);
  console.log(`  code entry visible: ${onCodeStep}`);
} catch (e) {
  console.log(`  could not drive the email step (${String(e).slice(0, 60)}) — please do it in the window`);
}

console.log("");
console.log("  ==> A browser window is open on the bluntly.ph login page.");
console.log("      Send yourself the code, enter it, and finish signing in.");
console.log("      I am waiting for the app to leave /login.");
console.log("");

let ok = false;
try {
  await page.waitForFunction(
    () => !location.pathname.startsWith("/login") && !location.pathname.startsWith("/signup"),
    null,
    { timeout: 8 * 60 * 1000, polling: 1000 },
  );
  ok = true;
} catch {
  console.log("  timed out waiting for sign-in.");
}

if (ok) {
  await page.waitForTimeout(2500);
  await ctx.storageState({ path: STATE });
  const at = new URL(page.url()).pathname;
  console.log(`  signed in — landed on ${at}`);
  console.log(`  session saved to ${STATE}`);
}

await browser.close();
process.exit(ok ? 0 : 1);
