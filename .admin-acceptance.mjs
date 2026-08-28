import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

/**
 * Full admin console acceptance: 8 screens x 5 viewports, plus the scroll
 * model, the queue workbench's behaviour, and the navigation audit.
 */
const STATE = process.argv[2], OUT = process.argv[3];
const BASE = "https://www.bluntly.ph";
const SCREENS = [
  ["Overview", "/moderate"],
  ["Review Queue", "/moderate/review-queue"],
  ["Products", "/moderate/products"],
  ["Reviewers", "/moderate/reviewers"],
  ["Affiliate Links", "/moderate/affiliate-links"],
  ["Honesty Fund", "/moderate/honesty-fund"],
  ["Analytics", "/moderate/analytics"],
  ["Activity Log", "/moderate/activity"],
];
const WIDTHS = [1440, 1280, 1024, 768, 393];
const DESKTOP = new Set([1440, 1280, 1024]);

fs.mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ storageState: STATE });
const p = await ctx.newPage();
const problems = [];
const rows = [];
const note = (m) => { problems.push(m); console.log(`  ✗ ${m}`); };

await p.goto(`${BASE}/moderate`, { waitUntil: "domcontentloaded", timeout: 45000 });
await p.waitForTimeout(2500);
if (new URL(p.url()).pathname.startsWith("/login")) {
  console.log("SESSION EXPIRED"); await b.close(); process.exit(2);
}

for (const width of WIDTHS) {
  console.log(`\n— ${width}px —`);
  await p.setViewportSize({ width, height: 860 });
  for (const [name, route] of SCREENS) {
    const errs = [], bad = [];
    p.removeAllListeners("console"); p.removeAllListeners("response");
    p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 80)); });
    p.on("response", (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url().replace(BASE,"").slice(0,60)}`); });

    const resp = await p.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 45000 });
    await p.waitForTimeout(2200);

    const m = await p.evaluate(() => {
      const doc = document.documentElement;
      const rail = document.querySelector("aside");
      const main = document.querySelector("main");
      const railBefore = rail ? Math.round(rail.getBoundingClientRect().top) : null;
      if (main) main.scrollTop = main.scrollHeight;
      const railAfter = rail ? Math.round(rail.getBoundingClientRect().top) : null;
      window.scrollTo(0, 3000);
      const winScroll = window.scrollY;
      window.scrollTo(0, 0);
      if (main) main.scrollTop = 0;
      // Is any table cell clipped by its container?
      let clipped = 0;
      for (const t of document.querySelectorAll("table")) {
        const box = t.closest("[class*=overflow]");
        if (!box) continue;
        const br = box.getBoundingClientRect();
        for (const cell of t.querySelectorAll("tbody tr:first-child td")) {
          const cr = cell.getBoundingClientRect();
          if (cr.right > br.right + 1) clipped++;
        }
      }
      return {
        innerH: window.innerHeight,
        scrollH: doc.scrollHeight,
        delta: doc.scrollHeight - doc.clientHeight,
        winScroll,
        railBefore, railAfter,
        railMoved: railBefore !== null && railAfter !== null ? Math.abs(railAfter - railBefore) : 0,
        mainScrollH: main ? main.scrollHeight : null,
        mainClientH: main ? main.clientHeight : null,
        clippedCells: clipped,
        railVisible: rail ? rail.getBoundingClientRect().width > 0 : false,
        drawerBtn: !!document.querySelector('button[aria-label="Open admin navigation"]'),
        failure: /unable to load|something went wrong|failed to load/i.test(document.body.innerText),
        overflowX: doc.scrollWidth > doc.clientWidth + 1,
      };
    });

    rows.push({ name, route, width, ...m });
    if (DESKTOP.has(width)) {
      if (m.winScroll > 0) note(`${route} @${width}: document scrolled to ${m.winScroll}`);
      if (m.railMoved > 1) note(`${route} @${width}: rail moved ${m.railMoved}px`);
      if (m.clippedCells > 0) note(`${route} @${width}: ${m.clippedCells} clipped table cell(s)`);
      if (!m.railVisible) note(`${route} @${width}: rail not visible on desktop`);
    } else {
      if (!m.drawerBtn && !m.railVisible) note(`${route} @${width}: no way to open navigation`);
    }
    if (m.overflowX) note(`${route} @${width}: horizontal document overflow`);
    if (m.failure) note(`${route} @${width}: visible failure state`);
    if (errs.length) note(`${route} @${width}: console error — ${errs[0]}`);
    if (bad.length) note(`${route} @${width}: ${bad[0]}`);
    if (resp?.status() !== 200) note(`${route} @${width}: HTTP ${resp?.status()}`);

    await p.screenshot({ path: path.join(OUT, `${name.replace(/\W+/g,"-")}-${width}.png`) });
    console.log(`  ${name.padEnd(16)} @${String(width).padEnd(5)} doc=${m.delta}px winScroll=${m.winScroll} rail=${m.railMoved}px main=${m.mainScrollH}/${m.mainClientH} clipped=${m.clippedCells} ${DESKTOP.has(width) ? (m.railVisible?"rail":"NO-RAIL") : (m.drawerBtn?"drawer":"no-drawer")}`);
  }
}

fs.writeFileSync(path.join(OUT, "admin-metrics.json"), JSON.stringify({ rows, problems }, null, 2));
console.log(`\n${problems.length === 0 ? "ADMIN ACCEPTANCE CLEAN" : `${problems.length} PROBLEM(S)`}`);
await b.close();
process.exit(problems.length === 0 ? 0 : 1);
