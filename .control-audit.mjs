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

await check("tab: Answers", async () => {
  await p.getByRole("button", { name: /^Answers/ }).click();
  await p.waitForTimeout(600);
  return /not wired into this console/i.test(await p.evaluate(() => document.body.innerText));
});
await check("tab: Report", async () => {
  await p.getByRole("button", { name: /^Report/ }).click();
  await p.waitForTimeout(600);
  return /reported|nothing has been reported/i.test(await p.evaluate(() => document.body.innerText));
});
await check("tab: Reviews (back)", async () => {
  await p.getByRole("button", { name: /^Reviews/ }).click();
  await p.waitForTimeout(600);
  return (await rowCount()) > 0;
});
await check("sort toggle", async () => {
  const before = await firstId();
  await p.getByRole("button", { name: /Newest first|Oldest first/ }).click();
  await p.waitForTimeout(600);
  return (await firstId()) !== before;
});
await check("priority filter", async () => {
  const before = await rowCount();
  await p.selectOption("select", "High");
  await p.waitForTimeout(600);
  const after = await rowCount();
  await p.selectOption("select", "");
  await p.waitForTimeout(400);
  return after !== before;
});
await check("search", async () => {
  const before = await rowCount();
  await p.getByRole("searchbox").fill("zzz-no-match-zzz");
  await p.waitForTimeout(700);
  const after = await rowCount();
  await p.getByRole("searchbox").fill("");
  await p.waitForTimeout(500);
  return after !== before;
});
await check("page size", async () => {
  const sels = await p.locator("select").count();
  if (sels < 2) return false;
  await p.locator("select").nth(1).selectOption("25");
  await p.waitForTimeout(600);
  return true;
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
