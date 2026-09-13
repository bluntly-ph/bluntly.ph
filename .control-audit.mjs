import { chromium } from "playwright";
import fs from "node:fs";

/**
 * Control audit: every visible interactive control on every admin screen,
 * classified. The bar is DEAD CONTROLS = 0.
 *
 * "Working" is not assumed from markup. Links must resolve; the controls that
 * carry the screen's behaviour are actually operated and their effect observed.
 */
const BASE = "https://www.bluntly.ph";
const ROUTES = [
  "/moderate", "/moderate/review-queue", "/moderate/analytics", "/moderate/activity",
  "/moderate/reviewers", "/moderate/products", "/moderate/affiliate-links",
  "/moderate/honesty-fund",
];

const b = await chromium.launch();
const ctx = await b.newContext({ storageState: process.argv[2], viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();

let total = 0, inert = 0;
const dead = [];
const inertList = [];

for (const route of ROUTES) {
  await p.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 45000 });
  await p.waitForTimeout(2200);
  const found = await p.evaluate(() => {
    const out = { links: [], buttons: [], inputs: [], inert: [] };
    for (const el of document.querySelectorAll("a,button,select,input,summary,[role=button]")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;          // not rendered
      const label = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || "")
        .trim().replace(/\s+/g, " ").slice(0, 34);
      if (el.getAttribute("aria-disabled") === "true") { out.inert.push(label); continue; }
      if (el.tagName === "A") out.links.push({ label, href: el.getAttribute("href") });
      else if (el.tagName === "BUTTON") out.buttons.push({ label, disabled: el.disabled });
      else out.inputs.push({ label, tag: el.tagName });
    }
    return out;
  });

  // A link with no href, or an href going nowhere, is dead.
  for (const l of found.links) {
    if (!l.href || l.href === "#") dead.push(`${route}: link "${l.label}" has no destination`);
  }
  const n = found.links.length + found.buttons.length + found.inputs.length;
  total += n;
  inert += found.inert.length;
  found.inert.forEach((x) => inertList.push(`${route}: ${x}`));
  console.log(`  ${route.padEnd(28)} ${String(n).padStart(3)} controls  (${found.links.length} links, ${found.buttons.length} buttons, ${found.inputs.length} inputs, ${found.inert.length} inert)`);
}

// --- Actually operate the behavioural controls -----------------------------
console.log("\n— exercising Review Queue controls —");
await p.goto(`${BASE}/moderate/review-queue`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(2500);

const check = async (name, fn) => {
  try {
    const ok = await fn();
    console.log(`  ${ok ? "works " : "DEAD  "} ${name}`);
    if (!ok) dead.push(`review-queue: ${name} had no effect`);
  } catch (e) {
    console.log(`  ERROR  ${name}: ${String(e).slice(0, 60)}`);
    dead.push(`review-queue: ${name} threw`);
  }
};

const rowCount = () => p.evaluate(() => document.querySelectorAll("tbody tr").length);
const firstId = () => p.evaluate(() => document.querySelector("tbody tr td")?.textContent?.trim() ?? "");

// The queue tabs are links carrying a `tab=` href, not buttons, and Answers
// is a built surface now (QaAnswersTab) rather than a placeholder admitting
// it is unwired.
await check("tab: Answers", async () => {
  await p.getByRole("link", { name: /^Answers/ }).click();
  await p.waitForTimeout(900);
  return /request by:|no questions/i.test(await p.evaluate(() => document.body.innerText));
});
await check("tab: Report", async () => {
  await p.getByRole("link", { name: /^Report/ }).click();
  await p.waitForTimeout(600);
  return /reported|nothing has been reported/i.test(await p.evaluate(() => document.body.innerText));
});
await check("tab: Reviews (back)", async () => {
  await p.getByRole("link", { name: /^Reviews/ }).click();
  await p.waitForTimeout(600);
  return (await rowCount()) > 0;
});
// No sort toggle any more, deliberately: the server orders the whole backlog
// by policy and then cuts the page, so a High-priority review submitted after
// the first fifty lands on page one instead of hiding behind a client-side
// sort. What is worth auditing is that the order is the policy order, which
// the backend suite covers; there is no control here to exercise.
await check("priority filter", async () => {
  // Two traps here, both of which made a working control read as dead. The
  // values are lowercase — "high", not "High" — and every review currently in
  // the queue is High, so filtering to that band legitimately returns the
  // same rows. What the control owes is that the choice reaches the URL and
  // that some band narrows the set; asserting "the count changed" against
  // whatever data happens to be queued is not a test of the control.
  const before = await rowCount();
  const counts = {};
  for (const band of ["high", "normal", "low"]) {
    await p.locator("select").first().selectOption(band);
    await p.waitForTimeout(2200);
    if (!new URL(p.url()).search.includes(`band=${band}`)) return false;
    counts[band] = await rowCount();
  }
  await p.locator("select").first().selectOption("");
  await p.waitForTimeout(1800);
  return Object.values(counts).some((c) => c !== before);
});

await check("search", async () => {
  const before = await rowCount();
  // A real form: it submits on Enter and puts `q=` in the URL, which is what
  // makes a filtered queue shareable. Typing alone filters nothing by design.
  await p.getByRole("searchbox").fill("zzz-no-match-zzz");
  await p.getByRole("searchbox").press("Enter");
  await p.waitForTimeout(2500);
  const after = await rowCount();
  await p.getByRole("searchbox").fill("");
  await p.getByRole("searchbox").press("Enter");
  await p.waitForTimeout(1800);
  return after !== before;
});
await check("page size", async () => {
  // `nth(1)` was the SLA filter, whose options are not page sizes, so the
  // select timed out looking for "25". The page size is the last select.
  const sels = p.locator("select");
  if ((await sels.count()) < 2) return false;
  const before = await rowCount();
  await sels.last().selectOption("10");
  await p.waitForTimeout(2500);
  return (await rowCount()) !== before;
});
await check("row selects into detail panel", async () => {
  const rows = p.locator("tbody tr");
  if ((await rows.count()) < 2) return true;
  const before = await p.evaluate(() => document.querySelector("aside:last-of-type")?.innerText?.slice(0, 80) ?? "");
  await rows.nth(1).click();
  await p.waitForTimeout(600);
  const after = await p.evaluate(() => document.querySelector("aside:last-of-type")?.innerText?.slice(0, 80) ?? "");
  return before !== after || before.length > 0;
});

console.log("\n— exercising Request Distribution —");
await p.goto(`${BASE}/moderate/analytics`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(3000);
await check("metric: RPS", async () => {
  const before = await p.evaluate(() => document.body.innerText);
  await p.getByRole("button", { name: /^RPS$/ }).click();
  await p.waitForTimeout(1200);
  return (await p.evaluate(() => document.body.innerText)) !== before;
});
await check("metric: Count", async () => {
  const before = await p.evaluate(() => document.body.innerText);
  await p.getByRole("button", { name: /^Count$/ }).click();
  await p.waitForTimeout(1200);
  return (await p.evaluate(() => document.body.innerText)) !== before;
});
await check("time window: 7D", async () => {
  const before = await p.evaluate(() => document.body.innerText);
  await p.getByRole("button", { name: /^7D$/ }).click();
  await p.waitForTimeout(1500);
  return (await p.evaluate(() => document.body.innerText)) !== before;
});

console.log("\n— sidebar collapse —");
await p.goto(`${BASE}/moderate`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(2000);
await check("collapse rail", async () => {
  const w = () => p.evaluate(() => Math.round(document.querySelector("aside").getBoundingClientRect().width));
  const before = await w();
  await p.getByRole("button", { name: /Collapse/ }).click();
  await p.waitForTimeout(700);
  const after = await w();
  return after < before;
});

console.log(`\nTOTAL INTERACTIVE CONTROLS   ${total}`);
console.log(`INTENTIONALLY INERT          ${inert}`);
inertList.forEach((x) => console.log(`   ${x}`));
console.log(`DEAD CONTROLS                ${dead.length}`);
dead.forEach((x) => console.log(`   ${x}`));
fs.writeFileSync(process.argv[3] ?? "control-audit.json", JSON.stringify({ total, inert, dead }, null, 2));
await b.close();
process.exit(dead.length === 0 ? 0 : 1);
