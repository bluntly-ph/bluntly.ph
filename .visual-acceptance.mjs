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

const SCREENS = [
  { route: "/dashboard", name: "dashboard", frame: "5572:7130",
    expect: [/wallet|balance|earn/i], controls: ['a[href*="/dashboard/"]'] },
  { route: "/dashboard/transfer", name: "transfer", frame: "5762:332",
    expect: [/est\.?\s*comm|withdraw/i], controls: ["button, [role=progressbar]"] },
  { route: "/dashboard/history", name: "history", frame: "5762:472",
    expect: [/all time income|historical bill/i], controls: ['a[href*="status="], details'] },
  { route: "/dashboard/reviews", name: "reviews", frame: "6159:1510",
    expect: [/review/i], controls: ['a[href="/dashboard"]'] },
  { route: "/dashboard/insights", name: "insights", frame: "5762:752",
    expect: [/streak/i], controls: ["svg, section"] },
  { route: "/moderate", name: "moderate", frame: "5017:1738",
    expect: [/queue|overview|honesty/i], controls: ['a[href*="/moderate"], button'] },
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
    let row = { ...screen, width, expect: undefined, controls: undefined };
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
          controlCount: document.querySelectorAll(cfg.controls).length,
          peso: (body.match(/₱[\d,]+(\.\d{2})?/g) || []).slice(0, 6),
          hasFigmaSample: /328\.04|2,?\s?426\.38|\b6 days\b/.test(body),
        };
      }, { controls: screen.controls.join(",") });

      const bodyText = await page.evaluate(() => document.body.innerText);
      const dataOk = screen.expect.every((re) => re.test(bodyText));
      const file = path.join(OUT, `${screen.name}-${width}.png`);
      await page.screenshot({ path: file, fullPage: true });

      row = { ...row, http: resp?.status(), ...m, dataOk,
              consoleErrors: [...consoleErrors], httpBad: [...httpBad], file: path.basename(file) };
      const flags = [
        m.imgBroken ? `${m.imgBroken} BROKEN IMG` : "",
        m.overflows ? "H-OVERFLOW" : "",
        consoleErrors.length ? `${consoleErrors.length} CONSOLE ERR` : "",
        httpBad.length ? `${httpBad.length} HTTP>=400` : "",
        !dataOk ? "EXPECTED CONTENT MISSING" : "",
        m.hasFigmaSample ? "FIGMA SAMPLE VALUE ON PAGE" : "",
        m.controlCount === 0 ? "NO CONTROLS" : "",
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
