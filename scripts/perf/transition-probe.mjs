#!/usr/bin/env node
/**
 * Client-side navigation and interaction timing — the part of "it feels laggy"
 * that a page-load audit cannot see.
 *
 *   node scripts/perf/transition-probe.mjs                            # production
 *   node scripts/perf/transition-probe.mjs http://127.0.0.1:3100 --runs 5
 *
 * Lighthouse measures a cold navigation. Most of a visit is not that: it is a
 * tap on a link inside an app that is already running, where the time is the
 * router fetching the next route's payload, React rendering it, and the
 * browser painting. For each journey this records, per run:
 *
 *   url     tap -> the URL changes (the router committed to the navigation)
 *   paint   tap -> the destination's own content is visible (a selector that
 *           only the destination renders, NOT the loading skeleton)
 *   rsc     the route payload request's duration, from Resource Timing
 *   inp     the longest Event Timing entry for the tap (input delay + handler
 *           + presentation) — a single-session lab observation, not field INP
 *
 * CONDITIONS (recorded in the output): mobile viewport 390x844, CPU slowed 4x
 * and the network held to 150 ms RTT / 1.6 Mbps through the DevTools protocol,
 * the same profile Lighthouse's mobile run simulates. Chromium only.
 *
 * READ-ONLY: GET navigations and clicks on ordinary links. No forms, no votes,
 * and never a `/r/` affiliate link (that records a click).
 */
import { chromium } from "@playwright/test";

const BASE = (process.argv.find((a) => /^https?:\/\//.test(a)) ?? "https://www.bluntly.ph").replace(/\/$/, "");
const runsIdx = process.argv.indexOf("--runs");
const RUNS = runsIdx > -1 ? Number(process.argv[runsIdx + 1]) : 3;

const REVIEW = "00000000-0000-0000-0000-0000000e0007";

/**
 * Each journey: where to start, what to tap, and a selector only the
 * destination renders. Selectors are structural, not copy, so data changes
 * do not break them.
 */
const JOURNEYS = [
  {
    name: "feed -> review",
    start: "/feed",
    tap: `main a[href^="/reviews/"]:not([href="/reviews/new"])`,
    arrived: (url) => /\/reviews\/[0-9a-f-]{36}$/.test(new URL(url).pathname),
    destination: "main h1",
  },
  {
    name: "search -> review",
    start: "/search",
    tap: `main a[href^="/reviews/"]:not([href="/reviews/new"])`,
    arrived: (url) => /\/reviews\/[0-9a-f-]{36}$/.test(new URL(url).pathname),
    destination: "main h1",
  },
  {
    name: "review -> seller/author profile",
    start: `/reviews/${REVIEW}`,
    tap: `main a[href^="/u/"]`,
    arrived: (url) => new URL(url).pathname.startsWith("/u/"),
    destination: "main h1",
  },
  {
    name: "home -> about (footer link)",
    start: "/",
    tap: `footer a[href="/about"]`,
    arrived: (url) => new URL(url).pathname === "/about",
    destination: "main h1",
  },
  {
    name: "questions -> question",
    start: "/questions",
    tap: `main a[href^="/questions/"]:not([href="/questions/new"])`,
    arrived: (url) => /\/questions\/[0-9a-f-]{36}$/.test(new URL(url).pathname),
    destination: "main h1",
  },
];

const median = (xs) => {
  const v = xs.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : Math.round((v[m - 1] + v[m]) / 2);
};

async function throttle(page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  return cdp;
}

async function once(browser, journey) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  await throttle(page);
  await page.goto(`${BASE}${journey.start}`, { waitUntil: "load", timeout: 90000 });
  // Let hydration and viewport prefetching settle, as a reader who scrolls a moment would.
  await page.waitForTimeout(2500);
  await page.evaluate(() => {
    window.__events = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__events.push({ name: e.name, duration: e.duration, start: e.startTime });
    }).observe({ type: "event", durationThreshold: 16, buffered: false });
  });

  // Only a link a reader can see: the desktop header keeps hidden copies in the DOM.
  const link = page.locator(journey.tap).filter({ visible: true }).first();
  if ((await link.count()) === 0) {
    await context.close();
    return { error: `nothing matches ${journey.tap}` };
  }
  const href = await link.getAttribute("href");
  await link.scrollIntoViewIfNeeded();
  const t0 = await page.evaluate(() => performance.now());
  const wall0 = Date.now();
  await link.tap();

  let urlAt = null;
  while (Date.now() - wall0 < 30000) {
    if (journey.arrived(page.url())) {
      urlAt = Date.now() - wall0;
      break;
    }
    await page.waitForTimeout(10);
  }
  let paintAt = null;
  try {
    await page.waitForFunction(
      ([sel, start]) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.height > 0 && performance.now() > start;
      },
      [journey.destination, t0],
      { timeout: 30000, polling: 16 },
    );
    paintAt = Math.round((await page.evaluate(() => performance.now())) - t0);
  } catch {
    /* recorded as null */
  }
  await page.waitForTimeout(300);
  const detail = await page.evaluate(
    ([start, path]) => {
      const rsc = performance
        .getEntriesByType("resource")
        .filter((r) => r.startTime >= start - 50 && r.name.includes(path) && r.name.includes("_rsc="))
        .map((r) => Math.round(r.duration));
      const taps = (window.__events ?? []).filter((e) => ["pointerdown", "pointerup", "click", "touchstart", "touchend"].includes(e.name));
      return { rsc, inp: taps.length ? Math.round(Math.max(...taps.map((e) => e.duration))) : null };
    },
    [t0, href.split("?")[0]],
  );
  await context.close();
  return { href, url: urlAt, paint: paintAt, rsc: detail.rsc.length ? Math.max(...detail.rsc) : null, inp: detail.inp };
}

const browser = await chromium.launch();
console.log(`transition probe — ${BASE} — ${new Date().toISOString()} — ${RUNS} runs`);
console.log("conditions: 390x844 mobile, CPU 4x, 150 ms RTT, 1.6 Mbps (CDP). Lab, single-session; not field INP.\n");
console.log("| journey | url ms (median, range) | content ms | rsc ms | tap event ms |");
console.log("| --- | --- | --- | --- | --- |");
for (const journey of JOURNEYS) {
  const rows = [];
  for (let i = 0; i < RUNS; i += 1) {
    try {
      rows.push(await once(browser, journey));
    } catch (e) {
      rows.push({ error: e.message.split(/\r?\n/)[0] });
    }
  }
  const ok = rows.filter((r) => !r.error);
  if (!ok.length) {
    console.log(`| ${journey.name} | ${rows[0].error} | | | |`);
    continue;
  }
  const cell = (k) => {
    const xs = ok.map((r) => r[k]).filter((x) => x != null);
    return xs.length ? `${median(xs)} (${Math.min(...xs)}–${Math.max(...xs)})` : "—";
  };
  console.log(`| ${journey.name} | ${cell("url")} | ${cell("paint")} | ${cell("rsc")} | ${cell("inp")} |`);
}
await browser.close();
