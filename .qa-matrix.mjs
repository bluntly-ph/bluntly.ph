import { chromium } from "playwright";

/**
 * QA-001 .. QA-012, re-run from scratch against production.
 *
 * The dispositions in docs/RELEASE_HANDOFF.md were recorded against earlier
 * builds. This asserts each one again on the current deployment rather than
 * carrying the old counts forward.
 *
 * Read-only. It never submits a review, never votes, and never publishes
 * anything; the one piece of state it touches is the signed-in account's own
 * draft map, which it snapshots and restores.
 */

const BASE = "https://www.bluntly.ph";
const STATE = process.argv[2];
const DRAFTS_KEY = "bluntly:review-drafts:v2";

const results = [];
const rec = (id, name, pass, detail = "") =>
  results.push({ id, name, pass, detail });

const b = await chromium.launch({ args: ["--no-sandbox"] });
const ctx = await b.newContext({
  storageState: STATE,
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 1,
});

const consoleErrors = [];
ctx.on("page", (pg) =>
  pg.on("console", (m) => {
    if (m.type() === "error" && !/eval\(\)/.test(m.text())) {
      consoleErrors.push(m.text().slice(0, 110));
    }
  }),
);

const open = async (path, wait = 3000, width = 390) => {
  const pg = await ctx.newPage();
  await pg.setViewportSize({ width, height: 844 });
  await pg.goto(BASE + path, { waitUntil: "domcontentloaded", timeout: 60000 });
  await pg.waitForTimeout(wait);
  return pg;
};

// ---------------------------------------------------------------- QA-001
{
  const p = await open("/search?q=fan", 4000);
  const m = await p.evaluate(() => {
    const imgs = [...document.querySelectorAll("main img")];
    const loaded = imgs.filter((i) => i.naturalWidth > 1).length;
    // "Write a review" is a CTA, not a result.
    const cards = [...document.querySelectorAll('a[href^="/reviews/"]')]
      .filter((a) => a.getAttribute("href") !== "/reviews/new")
      .map((a) => a.innerText.toLowerCase());
    return { imgs: imgs.length, loaded, cards: cards.length,
             relevant: cards.filter((t) => /fan|jisulife|cooling|breeze|portable/.test(t)).length };
  });
  rec("QA-001", "search images load", m.imgs > 0 && m.loaded === m.imgs,
      `${m.loaded}/${m.imgs} images decoded`);
  rec("QA-001", "search results match the keyword",
      m.cards === 0 || m.relevant > 0,
      `${m.relevant}/${m.cards} cards mention "fan"`);
  await p.close();
}

// ---------------------------------------------------------------- QA-005
{
  const p = await open("/", 3500);
  const m = await p.evaluate(() => {
    const foot = document.querySelector("footer");
    const t = foot?.innerText ?? "";
    const socials = ["reddit", "instagram", "facebook", "tiktok"]
      .filter((s) => t.toLowerCase().includes(s));
    const links = [...(foot?.querySelectorAll("a") ?? [])]
      .map((a) => a.getAttribute("href") ?? "")
      .filter((h) => /reddit|instagram|facebook|tiktok/i.test(h));
    return { socials, links, followUs: /follow us/i.test(t) };
  });
  rec("QA-005", "no social accounts claimed in the footer",
      m.socials.length === 0 && m.links.length === 0,
      m.socials.length ? `found ${m.socials.join(",")}` : "none");
  await p.close();
}

// ---------------------------------------------------------------- QA-007
for (const route of ["/about", "/how-it-works", "/faqs", "/articles"]) {
  const p = await open(route, 3000, 1280);
  const m = await p.evaluate(() => {
    const bad = [];
    for (const el of document.querySelectorAll("[data-cta], .prose a")) {
      const s = getComputedStyle(el);
      let bg = s.backgroundColor;
      let node = el;
      while (bg === "rgba(0, 0, 0, 0)" && node.parentElement) {
        node = node.parentElement;
        bg = getComputedStyle(node).backgroundColor;
      }
      if (s.color === bg) bad.push((el.textContent || "").trim().slice(0, 24));
    }
    return { bad, ctas: document.querySelectorAll("[data-cta]").length };
  });
  rec("QA-007", `CTA legible on ${route}`, m.bad.length === 0,
      m.bad.length ? `invisible: ${m.bad.join(" | ")}` : `${m.ctas} CTAs`);
  await p.close();
}

// ------------------------------------------------------- QA-008/009/010
{
  const p = await open("/search", 3000);
  // /search renders two visible comboboxes — the hero's and the page's — so
  // every step below must address the same one. Inspecting whichever
  // document.querySelector returns first reports on the other.
  const box = p.locator('input[role="combobox"]:visible').first();
  const boxIndex = 0;

  await box.fill("f");
  await p.waitForTimeout(1500);
  const oneChar = await p.locator('[role="option"]').count();
  rec("QA-010", "nothing requested below two characters", oneChar === 0,
      `${oneChar} options at 1 char`);

  await box.fill("fan");
  await p.waitForTimeout(2200);
  const opts = await p.locator('[role="option"]').count();
  rec("QA-009", "options appear at two or more characters", opts > 0, `${opts} options`);

  await box.press("ArrowDown");
  await p.waitForTimeout(400);
  const kb = await p.evaluate((i) => {
    const input = [...document.querySelectorAll('input[role="combobox"]')]
      .filter((e) => e.offsetParent !== null)[i];
    const id = input?.getAttribute("aria-activedescendant");
    const el = id ? document.getElementById(id) : null;
    return {
      active: !!id,
      focusStaysOnInput: document.activeElement === input,
      highlighted: el ? getComputedStyle(el).backgroundColor : null,
    };
  }, boxIndex);
  rec("QA-009", "keyboard highlights an option", kb.active && kb.focusStaysOnInput,
      `activedescendant=${kb.active}, focus on input=${kb.focusStaysOnInput}`);

  await box.press("Enter");
  await p.waitForTimeout(2500);
  const url = new URL(p.url());
  rec("QA-008", "selecting an option runs that search",
      url.pathname === "/search" && (url.searchParams.get("q") ?? "").length > 0,
      url.search || "(no query)");
  await p.close();
}

// ---------------------------------------------------------------- QA-006
{
  const p = await open("/feed", 4000);
  const href = await p.evaluate(() => {
    const a = [...document.querySelectorAll('a[href^="/reviews/"]')]
      .find((x) => x.getAttribute("href") !== "/reviews/new");
    return a?.getAttribute("href") ?? null;
  });
  await p.close();

  if (!href) {
    rec("QA-006", "Buy it here reaches a real listing", false, "no review found on /feed");
  } else {
    const r = await open(href, 4000);
    const buy = r.locator('a:has-text("Buy it here"), a:has-text("Buy")').first();
    const n = await buy.count();
    if (n === 0) {
      rec("QA-006", "Buy it here reaches a real listing", true,
          "no affiliate link on this review — nothing claimed, nothing broken");
    } else {
      const target = await buy.getAttribute("href");
      const resp = await ctx.request.get(new URL(target, BASE).toString(),
        { maxRedirects: 0, failOnStatusCode: false });
      const loc = resp.headers()["location"] ?? "";
      rec("QA-006", "Buy it here reaches a real listing",
          resp.status() >= 300 && resp.status() < 400 && /shopee|lazada/i.test(loc),
          `${resp.status()} -> ${loc.slice(0, 70)}`);
    }
    await r.close();
  }
}

// ---------------------------------------------------------------- QA-011
{
  const p = await open("/feed", 4000);
  const m = await p.evaluate(() => {
    const nums = [];
    // Only counts rendered as engagement metrics. "a sub-P4k board" inside a
    // review body is a price the reviewer typed, not a fabricated vote total.
    const metric = '[aria-label*="vote" i], [aria-label*="helpful" i], [data-metric]';
    for (const el of document.querySelectorAll(metric)) {
      const hit = (el.textContent || "").trim().match(/([0-9.]+)k/i);
      if (hit) nums.push(hit[1]);
    }
    return { thousands: nums.slice(0, 6) };
  });
  rec("QA-011", "no fabricated vote totals on the feed", m.thousands.length === 0,
      m.thousands.length ? `saw ${m.thousands.join(", ")}k` : "no k-scale counts");
  await p.close();
}

// ---------------------------------------------------------------- QA-012
{
  const p = await open("/", 3500, 1280);
  const m = await p.evaluate(() => {
    const nested = document.querySelectorAll("a button, button a").length;
    const flat = [...document.querySelectorAll("a[data-cta], button")]
      .filter((e) => !e.disabled)
      .filter((e) => getComputedStyle(e).cursor !== "pointer")
      .map((e) => (e.textContent || "").trim().slice(0, 22));
    return { nested, notPointer: flat };
  });
  rec("QA-012", "no button nested inside an anchor", m.nested === 0, `${m.nested} nested`);
  rec("QA-012", "clickable controls show a pointer cursor", m.notPointer.length === 0,
      m.notPointer.length ? m.notPointer.join(" | ") : "all pointer");
  await p.close();
}

// -------------------------------------------------- QA-002/003/004 (auth)
{
  const p = await open("/reviews/new", 3000);
  if (new URL(p.url()).pathname !== "/reviews/new") {
    for (const id of ["QA-002", "QA-003", "QA-004"]) {
      rec(id, "composer reachable", false, "SESSION INVALID — signed out");
    }
  } else {
    const ORIGINAL = await p.evaluate((k) => window.localStorage.getItem(k), DRAFTS_KEY);
    await p.evaluate((k) => window.localStorage.removeItem(k), DRAFTS_KEY);
    await p.reload({ waitUntil: "domcontentloaded" });
    await p.waitForTimeout(2500);

    const cont = () => p.getByRole("button", { name: /^Continue$/ });
    const toStep = async (n) => {
      await p.locator('input[placeholder^="e.g"]').first().fill("iPhone 15");
      await p.waitForTimeout(2000);
      await p.locator("li > button").filter({ hasText: /iphone/i }).first().click();
      await p.waitForTimeout(1500);
      await p.locator("textarea").first()
        .fill("Bought it in March and it has been my daily phone since, for photos on drives.");
      await cont().click(); await p.waitForTimeout(1100);
      if (n === 2) return;
      await p.getByRole("button", { name: /It depends/ }).click(); await p.waitForTimeout(500);
      await cont().click(); await p.waitForTimeout(1000);
      if (n === 3) return;
      await p.getByRole("button", { name: "4 stars" }).click(); await p.waitForTimeout(400);
      await cont().click(); await p.waitForTimeout(1300);
    };
    await toStep(4);

    // QA-002 — suggested phrases, selectable, not type-only
    const chips = p.locator("li > button[aria-pressed]");
    const chipCount = await chips.count();
    await chips.first().click();
    await p.waitForTimeout(400);
    const pressed = await chips.first().getAttribute("aria-pressed");
    const custom = await p.locator('input[placeholder^="Add a pro"]').count();
    rec("QA-002", "suggested pros/cons are offered", chipCount >= 10, `${chipCount} chips`);
    rec("QA-002", "a suggestion can be selected", pressed === "true", `aria-pressed=${pressed}`);
    rec("QA-002", "custom phrases still possible", custom > 0, `${custom} add-your-own inputs`);

    // QA-004 — the site must not claim immediate publication
    const claimsLive = await p.evaluate(() =>
      /now live|is live|published immediately/i.test(document.body.innerText));
    rec("QA-004", "composer does not claim immediate publication", !claimsLive,
        claimsLive ? "found a live claim" : "no live claim");

    // QA-003 — two drafts, both listed, previous one reopenable
    await p.evaluate((k) => {
      const now = Date.now();
      const mk = (slot, name) => ({
        slot,
        draft: { step: 1, discussion: `draft for ${name}`, verdict: null, rating: 0,
                 pros: "", cons: "", anti: "", target: "", title: "", photoUrl: null,
                 receiptKey: null, price: "",
                 product: { id: slot, canonical_name: name, image_url: null },
                 savedAt: now },
      });
      // readDrafts() parses Record<slot, Draft>. An array revives to nothing
      // and the resume list renders empty, which is not a product defect.
      const a = mk("qa3-a", "Tefal Pan QA-A");
      const b2 = mk("qa3-b", "Tefal Kettle QA-B");
      window.localStorage.setItem(k, JSON.stringify({
        [a.slot]: a.draft, [b2.slot]: b2.draft,
      }));
    }, DRAFTS_KEY);
    await p.goto(BASE + "/reviews/new", { waitUntil: "domcontentloaded" });
    await p.waitForTimeout(2500);
    const banners = await p.evaluate(() => ({
      a: /Tefal Pan QA-A/.test(document.body.innerText),
      b: /Tefal Kettle QA-B/.test(document.body.innerText),
      pickUps: [...document.querySelectorAll("button")]
        .filter((x) => /pick up/i.test(x.textContent || "")).length,
    }));
    rec("QA-003", "both saved drafts are listed", banners.a && banners.b,
        `A=${banners.a} B=${banners.b}`);
    rec("QA-003", "each draft can be reopened", banners.pickUps >= 2,
        `${banners.pickUps} resume actions`);

    if (banners.pickUps >= 1) {
      await p.locator("button").filter({ hasText: /pick up/i }).first().click();
      await p.waitForTimeout(1800);
      const reopened = await p.evaluate(() => /Tefal/.test(document.body.innerText));
      rec("QA-003", "reopening restores that draft", reopened,
          reopened ? "product restored" : "draft did not load");
    }

    await p.evaluate(([k, v]) => {
      if (v === null) window.localStorage.removeItem(k);
      else window.localStorage.setItem(k, v);
    }, [DRAFTS_KEY, ORIGINAL]);
  }
  await p.close();
}

await ctx.close();
await b.close();

const byId = {};
for (const r of results) (byId[r.id] ??= []).push(r);
console.log("\n=== QA-001 .. QA-012, fresh against production ===\n");
let failed = 0;
for (const id of Object.keys(byId).sort()) {
  const rows = byId[id];
  const bad = rows.filter((r) => !r.pass).length;
  failed += bad;
  console.log(`${id}  ${bad === 0 ? "PASS" : `${bad} FAILED`}`);
  for (const r of rows) {
    console.log(`   ${r.pass ? "ok  " : "FAIL"} ${r.name}${r.detail ? "  — " + r.detail : ""}`);
  }
}
console.log(`\nconsole errors: ${consoleErrors.length ? consoleErrors.slice(0, 3).join(" | ") : "none"}`);
console.log(`\n${failed === 0 ? "ALL CHECKS PASSED" : failed + " CHECK(S) FAILED"}`);
