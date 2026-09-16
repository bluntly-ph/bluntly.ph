/**
 * The sitemap sweep: every page in lib/site-map.ts, at the widths given, with
 * the session its access level needs.
 *
 *   node --experimental-strip-types scripts/audit-sweep.mjs
 *   WIDTHS=390,768,1440 ONLY=/search,/profile SHOT=1 node ... audit-sweep.mjs
 *
 * Env:
 *   BASE     default http://localhost:3000
 *   WIDTHS   default 390,768,1440
 *   ONLY     comma-separated route patterns to include (default: all)
 *   ACCESS   comma-separated access levels to include
 *   SHOT     1 to write a screenshot per route and width
 *   FULL     1 for full-page screenshots
 *   OUT      directory for screenshots and the JSON report
 *
 * Dynamic routes get a real id, discovered once from a listing page, so the
 * sweep never invents data. A route with no id available is reported as
 * skipped rather than passed.
 *
 * Local fixture sessions only: the cookie values are the scratch proxy's, never
 * a real credential.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { SITE_ROUTES } from "../lib/site-map.ts";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://localhost:3000";
const WIDTHS = (process.env.WIDTHS ?? "390,768,1440").split(",").map(Number);
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
const ACCESS = (process.env.ACCESS ?? "").split(",").filter(Boolean);
const SHOT = process.env.SHOT === "1";
const FULL = process.env.FULL === "1";
const OUT = process.env.OUT ?? "audit-out";
/** The fixture proxy answers the local session with fixture data, and 401s the rest. */
const SESSION = { "signed-in": "qa-local-fixture", "store-owner": "qa-local-fixture", moderator: "qa-local-moderator" };
/** The cookie belongs to whatever origin BASE names, not always localhost. */
const COOKIE_DOMAIN = new URL(BASE).hostname;
const IGNORE_CONSOLE = /status of 401|Failed to load resource: the server responded with a status of 401/;

const routes = SITE_ROUTES.filter(
  (r) => (ONLY.length === 0 || ONLY.includes(r.path)) && (ACCESS.length === 0 || ACCESS.includes(r.access)),
);

mkdirSync(OUT, { recursive: true });

/** Where to find a real id for each dynamic route, and the link that carries it. */
const DISCOVER = {
  "/reviews/[id]": { from: "/search", link: "a[href^='/reviews/']:not([href='/reviews/new'])" },
  "/questions/[id]": { from: "/questions", link: "a[href^='/questions/']:not([href='/questions/new'])" },
  // A reviewer link lives on a review, so this one hops through the review first.
  "/u/[id]": { fromRoute: "/reviews/[id]", link: "a[href^='/u/']" },
  "/sellers/[id]": { from: "/search?tab=sellers&q=qa", link: "a[href^='/sellers/']:not([href='/sellers/rate'])" },
  "/sellers/[id]/dashboard": { fromRoute: "/sellers/[id]", suffix: "/dashboard" },
};

const browser = await chromium.launch({ args: ["--disable-gpu"] });
const report = [];
const resolved = {};

async function discover(page) {
  for (const [pattern, how] of Object.entries(DISCOVER)) {
    if (how.fromRoute && how.suffix) {
      resolved[pattern] = resolved[how.fromRoute] ? resolved[how.fromRoute] + how.suffix : null;
      continue;
    }
    const from = how.fromRoute ? resolved[how.fromRoute] : how.from;
    if (!from) {
      resolved[pattern] = null;
      continue;
    }
    try {
      await page.goto(BASE + from, { waitUntil: "load", timeout: 45000 });
      await page.waitForTimeout(700);
      resolved[pattern] = await page.locator(how.link).first().getAttribute("href", { timeout: 4000 });
    } catch {
      resolved[pattern] = null;
    }
  }
}

for (const width of WIDTHS) {
  for (const access of ["public", "signed-out", "signed-in", "store-owner", "moderator"]) {
    const group = routes.filter((r) => r.access === access);
    if (group.length === 0) continue;
    const context = await browser.newContext({
      viewport: { width, height: width >= 1024 ? 900 : width >= 768 ? 1024 : 844 },
      deviceScaleFactor: 1,
    });
    const cookie = SESSION[access];
    if (cookie) {
      await context.addCookies([{ name: "bluntly_session", value: cookie, domain: COOKIE_DOMAIN, path: "/" }]);
    }
    const page = await context.newPage();
    if (Object.keys(resolved).length === 0) await discover(page);

    for (const route of group) {
      const target = route.path.includes("[") ? resolved[route.path] : route.path;
      if (!target) {
        report.push({ route: route.path, width, access, result: "SKIPPED", note: "no id available in this data set" });
        continue;
      }
      const errors = [];
      const onConsole = (m) => m.type() === "error" && !IGNORE_CONSOLE.test(m.text()) && errors.push(m.text().slice(0, 160));
      const onPageError = (e) => errors.push(`pageerror: ${e.message.slice(0, 160)}`);
      page.on("console", onConsole);
      page.on("pageerror", onPageError);
      let row;
      try {
        const res = await page.goto(BASE + target, { waitUntil: "load", timeout: 60000 });
        await page.waitForTimeout(600);
        const facts = await page.evaluate(() => ({
          overflowX: document.scrollingElement.scrollWidth - window.innerWidth,
          broken: [...document.images]
            .filter((i) => i.complete && i.naturalWidth === 0 && i.getAttribute("src"))
            .map((i) => i.getAttribute("src").slice(0, 80)),
          title: document.title,
          h1: document.querySelector("h1")?.textContent?.trim().slice(0, 60) ?? "",
          // The widest useful content block, to catch a phone column on a monitor.
          contentWidth: Math.round(
            Math.max(0, ...[...document.querySelectorAll("main, main > *, main > * > *")].map((el) => el.getBoundingClientRect().width)),
          ),
        }));
        const url = new URL(page.url());
        // A route that quietly lands somewhere else — a lost session bouncing to
        // /login, say — answers 200 and would otherwise be recorded as a pass.
        const landed = url.pathname;
        const wanted = target.split("?")[0];
        const redirected = landed !== wanted;
        row = {
          route: route.path,
          width,
          access,
          target,
          status: res?.status() ?? 0,
          landedOn: url.pathname + url.search,
          overflowX: facts.overflowX,
          broken: facts.broken,
          errors: [...new Set(errors)].slice(0, 4),
          h1: facts.h1,
          contentWidth: facts.contentWidth,
          redirected,
          result:
            (res?.status() ?? 0) >= 400 ||
            redirected ||
            facts.overflowX > 0 ||
            facts.broken.length > 0 ||
            errors.length > 0
              ? "FAIL"
              : "PASS",
          note: redirected ? `landed on ${landed}, not ${wanted}` : undefined,
        };
        if (SHOT) {
          const slug = route.path.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "home";
          await page.screenshot({ path: join(OUT, `${slug}-w${width}.png`), fullPage: FULL });
        }
      } catch (e) {
        row = { route: route.path, width, access, target, result: "FAIL", note: String(e.message).split("\n")[0].slice(0, 140) };
      }
      page.off("console", onConsole);
      page.off("pageerror", onPageError);
      report.push(row);
      const flag = row.result === "PASS" ? "ok  " : row.result;
      console.log(
        `${flag} w${width} ${route.path} -> ${row.status ?? ""} ${row.landedOn ?? row.note ?? ""} ovf=${row.overflowX ?? "-"} broken=${row.broken?.length ?? "-"} err=${row.errors?.length ?? "-"} content=${row.contentWidth ?? "-"}`,
      );
      for (const e of row.errors ?? []) console.log(`       ${e}`);
    }
    await context.close();
  }
}
await browser.close();
writeFileSync(join(OUT, "sweep.json"), JSON.stringify({ base: BASE, resolved, report }, null, 1));
const fails = report.filter((r) => r.result !== "PASS");
console.log(`\n${report.length} checks, ${fails.length} not passing`);
for (const f of fails) console.log(`  ${f.result} w${f.width} ${f.route} ${f.note ?? ""}`);
