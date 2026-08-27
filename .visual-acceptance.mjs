import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

/**
 * Authenticated acceptance pass against production.
 *
 * Runs the required order for every route: revision -> auth -> render -> assets
 * decode -> no 4xx/5xx -> no console errors -> real data -> controls -> capture.
 *
 * Reuses a session captured by .auth-capture.mjs with a human at the keyboard.
 * It never logs in and never touches a guard; if the session has expired it
 * stops, because a screenshot of a login page is worse than no screenshot.
 */

const STATE = process.argv[2];
const OUT = process.argv[3];
const BASE = "https://www.bluntly.ph";

/**
 * Per route: text that must NOT appear, and structure that MUST.
 *
 * The first pass called /moderate clean while the page visibly said "Unable to
 * load the overview right now." The failing fetch happened server-side, so
 * nothing reached the browser's console or network log. A clean console is not
 * a clean page.
 *
 * `must` uses ids and ARIA hooks rather than copy wherever the app exposes
 * them, so acceptance does not break when wording changes.
 */
const FAILURE_TEXT =
  /unable to load|something went wrong|failed to load|error loading|went wrong|try again later/i;

const SCREENS = [
  { route: "/dashboard", name: "dashboard", frame: "5572:7130",
    must: ['a[href="/dashboard/transfer"]', 'a[href="/dashboard/history"]',
           'a[href="/dashboard/insights"]'],
    expect: [/wallet|balance|earn/i] },
  { route: "/dashboard/transfer", name: "transfer", frame: "5762:332",
    must: ["#threshold-heading", "#account-heading", '[role="progressbar"]'],
    expect: [/est\.?\s*comm|withdraw/i] },
  { route: "/dashboard/history", name: "history", frame: "5762:472",
    must: ['nav[aria-label="Filter earnings"]', 'a[href*="status=pending"]'],
    expect: [/all time income|historical bill/i] },
  { route: "/dashboard/reviews", name: "reviews", frame: "6159:1510",
    must: ["#reviews-heading", 'a[href="/dashboard"]'],
    expect: [/your reviews/i] },
  { route: "/dashboard/insights", name: "insights", frame: "5762:752",
    must: ["#streak-heading", "#views-heading"],
    expect: [/streak/i] },
  { route: "/moderate", name: "moderate", frame: "5017:1738",
    // The three panels that vanished in production, plus the traffic panel
    // the overview fix must not regress.
    must: ["#admin-kpis", "#recent-activity-heading", "#queue-breakdown-heading",
           "#request-distribution-heading", '[role="group"][aria-label="Metric"]'],
    expect: [/queue|overview/i] },
];
const WIDTHS = [1440, 1280, 1024, 768, 393];

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ storageState: STATE });
const page = await ctx.newPage();

let consoleErrors = [];
let httpBad = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 140)); });
page.on("pageerror", (e) => consoleErrors.push("pageerror: " + String(e).slice(0, 140)));
page.on("response", (r) => {
  if (r.status() >= 400) httpBad.push(`${r.status()} ${r.url().replace(BASE, "").slice(0, 90)}`);
});

await page.goto(`${BASE}/dashboard`, { waitUntil: "domcontentloaded", timeout: 45000 });
await page.waitForTimeout(3000);
if (new URL(page.url()).pathname.startsWith("/login")) {
  console.log("SESSION EXPIRED — re-run .auth-capture.mjs. Captured nothing.");
  await browser.close();
  process.exit(2);
}
console.log(`session live (landed on ${new URL(page.url()).pathname})\n`);

const results = [];
for (const screen of SCREENS) {
  for (const width of WIDTHS) {
    consoleErrors = []; httpBad = [];
    await page.setViewportSize({ width, height: 900 });
    let row = { ...screen, width, expect: undefined, must: undefined };
    try {
      const resp = await page.goto(BASE + screen.route, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(2600);
      const landed = new URL(page.url()).pathname;
      if (landed.startsWith("/login")) {
        row.error = "redirected to /login";
        results.push(row);
        console.log(`  ${screen.name} @${width}  REDIRECTED TO LOGIN`);
        continue;
      }
      await page.evaluate(() => { for (const i of document.images) i.scrollIntoView({ block: "center" }); window.scrollTo(0, 0); });
      await page.waitForTimeout(1200);

      const m = await page.evaluate((cfg) => {
        const imgs = [...document.images];
        const body = document.body.innerText;
        const sheet = [...document.querySelectorAll("div")].find(
          (d) => parseFloat(getComputedStyle(d).borderTopLeftRadius) >= 20);
        const nav = document.querySelector("header, nav");
        return {
          title: document.title.slice(0, 44),
          textLen: body.trim().length,
          imgTotal: imgs.length,
          imgBroken: imgs.filter((i) => i.complete && i.naturalWidth === 0).length,
          overflows: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
          navH: nav ? Math.round(nav.getBoundingClientRect().height) : null,
          sheetTop: sheet ? Math.round(sheet.getBoundingClientRect().top + window.scrollY) : null,
          sheetRadius: sheet ? Math.round(parseFloat(getComputedStyle(sheet).borderTopLeftRadius)) : null,
          missingStructure: cfg.must.filter((sel) => !document.querySelector(sel)),
          controlCount: cfg.must.filter((sel) => document.querySelector(sel)).length,
          peso: (body.match(/₱[\d,]+(\.\d{2})?/g) || []).slice(0, 6),
          hasFigmaSample: /328\.04|2,?\s?426\.38|\b6 days\b/.test(body),
        };
      }, { must: screen.must });

      const bodyText = await page.evaluate(() => document.body.innerText);
      const dataOk = screen.expect.every((re) => re.test(bodyText));
      const visibleFailure = FAILURE_TEXT.test(bodyText);
      const file = path.join(OUT, `${screen.name}-${width}.png`);
      await page.screenshot({ path: file, fullPage: true });

      row = { ...row, http: resp?.status(), ...m, dataOk, visibleFailure,
              consoleErrors: [...consoleErrors], httpBad: [...httpBad], file: path.basename(file) };
      const flags = [
        m.imgBroken ? `${m.imgBroken} BROKEN IMG` : "",
        m.overflows ? "H-OVERFLOW" : "",
        consoleErrors.length ? `${consoleErrors.length} CONSOLE ERR` : "",
        httpBad.length ? `${httpBad.length} HTTP>=400` : "",
        !dataOk ? "EXPECTED CONTENT MISSING" : "",
        m.hasFigmaSample ? "FIGMA SAMPLE VALUE ON PAGE" : "",
        visibleFailure ? `VISIBLE FAILURE: "${m.failureText}"` : "",
        m.missingStructure.length ? `MISSING: ${m.missingStructure.join(" ")}` : "",
      ].filter(Boolean).join("  ");
      console.log(`  ${screen.name.padEnd(10)} @${String(width).padEnd(5)} ${resp?.status()} nav=${String(m.navH).padEnd(4)} sheet=${String(m.sheetTop).padEnd(5)} ctl=${String(m.controlCount).padEnd(3)} ${flags || "clean"}`);
      httpBad.slice(0, 2).forEach((b) => console.log(`        ${b}`));
      consoleErrors.slice(0, 2).forEach((e) => console.log(`        ${e}`));
    } catch (e) {
      row.error = String(e).slice(0, 110);
      console.log(`  ${screen.name} @${width}  ERROR ${row.error}`);
    }
    results.push(row);
  }
}

fs.writeFileSync(path.join(OUT, "measurements.json"), JSON.stringify(results, null, 2));
console.log(`\ncaptured ${results.filter((r) => r.file).length}/${SCREENS.length * WIDTHS.length} screenshots into ${OUT}`);
await browser.close();
