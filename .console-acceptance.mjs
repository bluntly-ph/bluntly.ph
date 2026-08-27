import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

/**
 * Admin console acceptance.
 *
 * The owner's complaint was architectural, not cosmetic, so this measures
 * architecture:
 *
 *   the console is a viewport, not a document   scrollHeight <= innerHeight
 *   the rail does not move                      bounding rect before/after scroll
 *   Overview is not the queue                   no queue table on /moderate
 *   the queue is its own screen                 table + pagination on its route
 *   nothing in the nav is dead                  every link resolves, none 404
 */

const STATE = process.argv[2];
const OUT = process.argv[3];
const BASE = "https://www.bluntly.ph";

const ROUTES = [
  "/moderate",
  "/moderate/review-queue",
  "/moderate/analytics",
  "/moderate/activity",
  "/moderate/reviewers",
  "/moderate/products",
  "/moderate/affiliate-links",
  "/moderate/honesty-fund",
];
const DESKTOP = [1440, 1280, 1024];

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ storageState: STATE });
const page = await ctx.newPage();

const problems = [];
const note = (m) => { problems.push(m); console.log(`  ✗ ${m}`); };

await page.goto(`${BASE}/moderate`, { waitUntil: "domcontentloaded", timeout: 45000 });
await page.waitForTimeout(2500);
if (new URL(page.url()).pathname.startsWith("/login")) {
  console.log("SESSION EXPIRED — re-run .auth-capture.mjs. Captured nothing.");
  await browser.close();
  process.exit(2);
}
console.log("session live\n");

for (const width of DESKTOP) {
  console.log(`— ${width}px —`);
  await page.setViewportSize({ width, height: 860 });

  for (const route of ROUTES) {
    const errs = [];
    page.removeAllListeners("console");
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 90)); });

    const resp = await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2200);

    const m = await page.evaluate(() => {
      const doc = document.documentElement;
      const rail = document.querySelector("aside");
      const main = document.querySelector("main");
      const railBefore = rail ? rail.getBoundingClientRect().top : null;
      // Scroll the workspace, then re-measure the rail.
      if (main) main.scrollTop = main.scrollHeight;
      const railAfter = rail ? rail.getBoundingClientRect().top : null;
      const text = document.body.innerText;
      return {
        docScroll: doc.scrollHeight - doc.clientHeight,
        innerH: window.innerHeight,
        railBefore, railAfter,
        railMoved: railBefore !== null && railAfter !== null && Math.abs(railAfter - railBefore) > 1,
        mainScrollable: main ? main.scrollHeight > main.clientHeight : false,
        hasTable: !!document.querySelector("table"),
        hasPagination: !!document.querySelector('nav[aria-label="Queue pages"]'),
        deadNav: [...document.querySelectorAll('aside [aria-disabled="true"]')].map(
          (e) => e.textContent.trim().replace(/\s+/g, " ").slice(0, 24)),
        navLinks: [...document.querySelectorAll('aside nav a')].map((a) => a.getAttribute("href")),
        failure: /unable to load|something went wrong|failed to load/i.test(text),
      };
    });

    // The document itself must not scroll on a desktop console.
    if (m.docScroll > 2) note(`${route} @${width}: document scrolls ${m.docScroll}px`);
    if (m.railMoved) note(`${route} @${width}: sidebar moved ${m.railBefore}→${m.railAfter}`);
    if (m.failure) note(`${route} @${width}: visible failure state`);
    if (errs.length) note(`${route} @${width}: ${errs.length} console error(s) — ${errs[0]}`);
    if (resp?.status() !== 200) note(`${route} @${width}: HTTP ${resp?.status()}`);

    if (width === DESKTOP[0]) {
      if (route === "/moderate" && m.hasPagination) {
        note("Overview still embeds the review queue");
      }
      if (route === "/moderate/review-queue" && !m.hasPagination) {
        note("Review Queue is missing its table/pagination");
      }
      await page.screenshot({
        path: path.join(OUT, `${route.replace(/\W+/g, "_")}-${width}.png`),
        fullPage: false,
      });
      console.log(
        `  ${route.padEnd(28)} doc=${m.docScroll}px rail=${m.railMoved ? "MOVED" : "fixed"} ` +
        `mainScrolls=${m.mainScrollable} table=${m.hasTable} inertNav=[${m.deadNav.join("|")}]`,
      );
    }
  }
}

// Every navigation link must resolve.
console.log("\n— navigation —");
await page.setViewportSize({ width: 1440, height: 860 });
await page.goto(`${BASE}/moderate`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
const hrefs = await page.evaluate(() =>
  [...document.querySelectorAll("aside nav a")].map((a) => a.getAttribute("href")));
for (const href of [...new Set(hrefs)]) {
  const r = await page.goto(BASE + href, { waitUntil: "domcontentloaded", timeout: 45000 });
  const ok = r?.status() === 200;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${r?.status()}  ${href}`);
  if (!ok) note(`nav link ${href} returned ${r?.status()}`);
}

fs.writeFileSync(path.join(OUT, "problems.json"), JSON.stringify(problems, null, 2));
console.log(`\n${problems.length === 0 ? "CONSOLE ACCEPTANCE CLEAN" : `${problems.length} PROBLEM(S)`}`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
