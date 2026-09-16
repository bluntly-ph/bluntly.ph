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
  // 4000, not 400: the first 400 characters are the sidebar, the header and
  // the tab labels, which are identical on every tab. A tab that swapped the
  // whole table underneath them still looked unchanged.
  text: document.body.innerText.replace(/\s+/g, " ").slice(0, 4000),
  rows: document.querySelectorAll("tbody tr").length,
  active: [...document.querySelectorAll('[aria-current="page"]')].map(e => e.textContent.trim().slice(0,12)).join(","),
}));

const reviews = await snapshot();
ok("Reviews tab shows the table", reviews.rows > 0, `${reviews.rows} rows`);

// Answers used to be a placeholder reading "not wired into this console". It
// is a real tab now (QaAnswersTab, frame 6532:278), and Report became one on
// 2026-09-16 when reports gained decisions (owner §30) — so for both the
// honest-state check is that the surface renders, not that it admits to being
// unbuilt. Support is still an honest placeholder.
for (const [label, expect] of [
  ["Answers", /request by:|no questions/i],
  ["Report", /report|dismiss|escalate/i],
  ["Support", /no support-ticket system/i],
]) {
  // The queue tabs are links, not buttons: they carry a `tab=` href and
  // change the URL, which is what makes a tab shareable and back-able.
  await p.getByRole("link", { name: new RegExp("^" + label) }).click();
  await p.waitForTimeout(800);
  const s = await snapshot();
  ok(`${label} tab changes the view`, s.text !== reviews.text, `rows ${reviews.rows}→${s.rows}`);
  ok(`${label} tab shows an honest state`, expect.test(await p.evaluate(() => document.body.innerText)));
  ok(`${label} tab marks itself active`, s.active.includes(label));
}
await p.getByRole("link", { name: /^Reviews/ }).click();
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
// `:visible` matters: the desktop sidebar is the same markup and stays in the
// DOM at 393, so an unscoped `aside nav a` matches both it and the drawer.
const navCount = await p.locator("aside nav a:visible").count();
ok("all admin routes reachable from the drawer", navCount >= 8, `${navCount} links`);

await p.locator('aside nav a[href="/moderate/analytics"]:visible').first().click();
await p.waitForTimeout(2500);
ok("selecting a route navigates", new URL(p.url()).pathname === "/moderate/analytics", p.url().replace(BASE, ""));
ok("drawer closes after selection", await p.locator('button[aria-label="Close admin navigation"]').count() === 0);

console.log(`\n${fails.length === 0 ? "FINAL CHECKS CLEAN" : fails.length + " FAILURE(S): " + fails.join("; ")}`);
await b.close();
process.exit(fails.length === 0 ? 0 : 1);
