import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

/**
 * The authenticated visual acceptance pass.
 *
 * Reuses a session captured by .auth-capture.mjs with a human at the keyboard.
 * It never logs in, never mints a token, never touches a guard: if the saved
 * session has expired it stops and says so, because a screenshot of /login
 * proving nothing is worse than no screenshot at all.
 *
 * For every screen at every width it captures a full-page PNG and measures the
 * chrome, so the comparison against Figma rests on rendered pixels and real
 * geometry rather than on reading the CSS and asserting intent.
 */

const STATE = process.argv[2];
const OUT = process.argv[3];
const BASE = "https://www.bluntly.ph";

const SCREENS = [
  { route: "/dashboard", name: "dashboard", frame: "5572:7130" },
  { route: "/dashboard/transfer", name: "transfer", frame: "5762:332" },
  { route: "/dashboard/history", name: "history", frame: "5762:472" },
  { route: "/dashboard/reviews", name: "reviews", frame: "6159:1510" },
  { route: "/dashboard/insights", name: "insights", frame: "5762:752" },
  { route: "/moderate", name: "moderate", frame: "5017:1738" },
];
const WIDTHS = [1440, 1280, 1024, 768, 393];

fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ storageState: STATE });
const page = await ctx.newPage();

// Prove the session is live before capturing anything.
await page.goto(`${BASE}/dashboard`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(2500);
if (new URL(page.url()).pathname.startsWith("/login")) {
  console.log("SESSION EXPIRED — re-run .auth-capture.mjs. Captured nothing.");
  await browser.close();
  process.exit(2);
}
console.log(`session live (landed on ${new URL(page.url()).pathname})\n`);

const results = [];

for (const screen of SCREENS) {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    const url = `${BASE}${screen.route}`;
    let entry = { ...screen, width };
    try {
      const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
      await page.waitForTimeout(1200);
      const landed = new URL(page.url()).pathname;
      if (landed.startsWith("/login")) {
        entry.error = "redirected to /login";
        results.push(entry);
        console.log(`  ${screen.name} @${width}  REDIRECTED TO LOGIN`);
        continue;
      }
      const file = path.join(OUT, `${screen.name}-${width}.png`);
      await page.screenshot({ path: file, fullPage: true });

      // Measured geometry, not asserted intent.
      const m = await page.evaluate(() => {
        const px = (el, prop) => el ? Math.round(parseFloat(getComputedStyle(el)[prop])) : null;
        const nav = document.querySelector("header, nav");
        const sheet = [...document.querySelectorAll("div")].find(
          d => parseFloat(getComputedStyle(d).borderTopLeftRadius) >= 20);
        const doc = document.documentElement;
        return {
          status: document.title,
          scrollW: doc.scrollWidth,
          clientW: doc.clientWidth,
          overflows: doc.scrollWidth > doc.clientWidth + 1,
          navH: nav ? Math.round(nav.getBoundingClientRect().height) : null,
          sheetRadius: px(sheet, "borderTopLeftRadius"),
          h1: (document.querySelector("h1")?.textContent || "").trim().slice(0, 60),
          headings: [...document.querySelectorAll("h2")].map(h => h.textContent.trim().slice(0, 28)),
          brokenImgs: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
          imgCount: document.images.length,
        };
      });
      entry = { ...entry, http: resp?.status(), ...m, file: path.basename(file) };
      const flags = [
        m.overflows ? "H-OVERFLOW" : "",
        m.brokenImgs > 0 ? `${m.brokenImgs} BROKEN IMG` : "",
      ].filter(Boolean).join(" ");
      console.log(`  ${screen.name.padEnd(10)} @${String(width).padEnd(5)} nav=${String(m.navH).padEnd(4)} radius=${String(m.sheetRadius).padEnd(4)} imgs=${m.imgCount} ${flags}`);
    } catch (e) {
      entry.error = String(e).slice(0, 100);
      console.log(`  ${screen.name} @${width}  ERROR ${entry.error}`);
    }
    results.push(entry);
  }
}

fs.writeFileSync(path.join(OUT, "measurements.json"), JSON.stringify(results, null, 2));
console.log(`\ncaptured ${results.filter(r => r.file).length}/${SCREENS.length * WIDTHS.length} screenshots into ${OUT}`);
await browser.close();
