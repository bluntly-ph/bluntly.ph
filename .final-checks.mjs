import { chromium } from "playwright";
const BASE = "https://www.bluntly.ph";
const b = await chromium.launch();
const ctx = await b.newContext({ storageState: process.argv[2] });
const p = await ctx.newPage();
const fails = [];
const ok = (n, c, detail = "") => { console.log(`  ${c ? "PASS" : "FAIL"}  ${n}${detail ? "  — " + detail : ""}`); if (!c) fails.push(n); };

// --- The four tabs must each change the view, not just the label ----------
console.log("Review Queue tabs (each must change the view):");
await p.setViewportSize({ width: 1440, height: 900 });
await p.goto(`${BASE}/moderate/review-queue`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(2500);

const snapshot = () => p.evaluate(() => ({
  text: document.body.innerText.replace(/\s+/g, " ").slice(0, 400),
  rows: document.querySelectorAll("tbody tr").length,
  active: [...document.querySelectorAll('[aria-current="page"]')].map(e => e.textContent.trim().slice(0,12)).join(","),
}));

const reviews = await snapshot();
ok("Reviews tab shows the table", reviews.rows > 0, `${reviews.rows} rows`);

for (const [label, expect] of [["Answers", /not wired into this console/i], ["Report", /reported|nothing has been reported/i], ["Support", /no support-ticket system/i]]) {
  await p.getByRole("button", { name: new RegExp("^" + label) }).click();
  await p.waitForTimeout(800);
  const s = await snapshot();
  ok(`${label} tab changes the view`, s.text !== reviews.text, `rows ${reviews.rows}→${s.rows}`);
  ok(`${label} tab shows an honest state`, expect.test(await p.evaluate(() => document.body.innerText)));
  ok(`${label} tab marks itself active`, s.active.includes(label));
}
await p.getByRole("button", { name: /^Reviews/ }).click();
await p.waitForTimeout(700);
ok("returning to Reviews restores the table", (await snapshot()).rows > 0);

// --- Date column present at every desktop width ---------------------------
console.log("\nDate column:");
for (const w of [1440, 1280, 1024]) {
  await p.setViewportSize({ width: w, height: 900 });
  await p.goto(`${BASE}/moderate/review-queue`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2200);
  const r = await p.evaluate(() => {
    const t = document.querySelector("table");
    if (!t) return { visible: false, clipped: -1 };
    const box = t.closest("[class*=overflow]");
    const br = box.getBoundingClientRect();
    const cells = [...t.querySelectorAll("tbody tr td:last-child")];
    const clipped = cells.filter(c => c.getBoundingClientRect().right > br.right + 1).length;
    const header = [...t.querySelectorAll("thead th")].pop();
    return { visible: header?.textContent.trim() === "Date", clipped, hOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 };
  });
  ok(`Date column at ${w}`, r.visible && r.clipped === 0 && !r.hOverflow, `clipped=${r.clipped} hOverflow=${r.hOverflow}`);
}

// --- Mobile drawer: the defect that superseded 02a6f65 --------------------
console.log("\nMobile navigation at 393:");
await p.setViewportSize({ width: 393, height: 850 });
await p.goto(`${BASE}/moderate`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(2500);

const trigger = p.locator('button[aria-label="Open admin navigation"]');
ok("drawer trigger exists", await trigger.count() === 1);
const covered = await p.evaluate(() => {
  const btn = document.querySelector('button[aria-label="Open admin navigation"]');
  if (!btn) return null;
  const r = btn.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const top = document.elementFromPoint(cx, cy);
  return { onTop: btn.contains(top) || top === btn, top: top?.tagName + "." + (top?.className||"").toString().slice(0,30) };
});
ok("drawer trigger is not covered by the site tab bar", covered?.onTop, covered?.top);

await trigger.click();
await p.waitForTimeout(700);
ok("drawer opens", await p.locator("aside nav").count() > 0);
const navCount = await p.locator("aside nav a").count();
ok("all admin routes reachable from the drawer", navCount >= 8, `${navCount} links`);

await p.locator('aside nav a[href="/moderate/analytics"]').click();
await p.waitForTimeout(2500);
ok("selecting a route navigates", new URL(p.url()).pathname === "/moderate/analytics", p.url().replace(BASE, ""));
ok("drawer closes after selection", await p.locator('button[aria-label="Close admin navigation"]').count() === 0);

console.log(`\n${fails.length === 0 ? "FINAL CHECKS CLEAN" : fails.length + " FAILURE(S): " + fails.join("; ")}`);
await b.close();
process.exit(fails.length === 0 ? 0 : 1);
