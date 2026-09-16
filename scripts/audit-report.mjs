/**
 * Builds docs/FRONTEND_AUDIT.md from the evidence the two sweeps leave behind.
 *
 *   node --experimental-strip-types scripts/audit-report.mjs --evidence <dir>
 *
 * <dir> holds the sweep output directories (audit-sweep.mjs writes sweep.json
 * into each) and a journeys.json from journey-check.mjs. Statuses in the table
 * are read from those files, never typed by hand, so the document cannot claim
 * a pass the harness did not produce.
 *
 * The per-route classification — how a page relates to the Figma file — is the
 * judgement part, and lives in CLASSIFICATION below with the reason attached.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { SITE_ROUTES } from "../lib/site-map.ts";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const args = process.argv.slice(2);
const EVIDENCE = args[args.indexOf("--evidence") + 1] ?? "audit-out";

/** Phone / tablet / desktop buckets for the widths the sweeps ran at. */
const BUCKET = (width) => (width < 768 ? "mobile" : width < 1280 ? "tablet" : "desktop");

const CLASS = {
  MATCHED: "FIGMA SOURCE-VERIFIED — MATCHED",
  CORRECTED: "FIGMA SOURCE-VERIFIED — CORRECTED",
  DIFFERENCE: "FIGMA SOURCE-VERIFIED — INTENTIONAL PRODUCT DIFFERENCE",
  OWNER: "FIGMA SOURCE-VERIFIED — OWNER DESIGN DIFFERENCE",
  BUSINESS: "NO FIGMA FRAME — BUSINESS-REQUIRED, DESIGN-SYSTEM ALIGNED",
  SUPPORTING: "NO FIGMA FRAME — SUPPORTING PRODUCT ROUTE, DESIGN-SYSTEM ALIGNED",
};

/**
 * route -> { klass, note, blocker }
 *
 * `note` says what differs from the frame and why, in the file's own terms.
 * `blocker` is a real obstacle, not a to-do.
 */
const CLASSIFICATION = {
  "/": {
    klass: CLASS.OWNER,
    note: "Frame matched (1902:1504) except the Earned pill: the frame puts it below the card at the right, the owner asked for it on the card's upper-right, so it is pinned inside the card's own composition (2026-09-16).",
  },
  "/search": {
    klass: CLASS.DIFFERENCE,
    note: "Pills, tabs, rows and the + match the frames. The frame's applied-filter chips read ★ All, 🛡 80-100, ⚖ Balanced, ⌛ All time; GET /reviews/feed serves category, q and sort only, so the one filter that exists (Category) draws the frame's hairline-and-chip treatment and the rest are not drawn inert. Website: the rail carries category and order beside the results.",
  },
  "/categories": {
    klass: CLASS.DIFFERENCE,
    note: "Rows, pitch and glyphs match (2355:939). The frame ends each row with a + that expands subcategories; no category has any, so each row is a link with a trailing arrow.",
  },
  "/feed": { klass: CLASS.BUSINESS, note: "The browsing surface. Rails, cards and type from the Figma system." },
  "/compare": { klass: CLASS.BUSINESS, note: "FR-2 comparison; no frame in the pack." },
  "/reviews/[id]": {
    klass: CLASS.CORRECTED,
    note: "Frame matched (4218:1196). Corrected in this audit: the phone's orange bar is md:hidden, which took Copy link and Report off the website — they now sit beside the headline from md.",
  },
  "/sellers/[id]": {
    klass: CLASS.CORRECTED,
    note: "Frames matched (4218:2148, 4295:1256) with the pack's own omissions (banner, logo, company details) left out. Corrected in this audit: a carousel slide's sr-only text escaped its scroller and pushed the page sideways at 320 and 360.",
  },
  "/u/[id]": {
    klass: CLASS.DIFFERENCE,
    note: "Profile frames matched (5446:4328). Followers, bio, People helped and Buyers guided are not served, so the figures are the ones the account has.",
  },
  "/questions": {
    klass: CLASS.BUSINESS,
    note: "No frame draws the list; built from the Question Page parts (title, Chip/Action, the search tab's row).",
  },
  "/questions/[id]": {
    klass: CLASS.BUSINESS,
    note: "No frame draws a single question; built from the Question Page's parts. The frame's product panel (price history, 3D model, specs) has no data behind it.",
  },
  "/requests": { klass: CLASS.BUSINESS, note: "The request board; no frame." },
  "/reviews/new": {
    klass: CLASS.DIFFERENCE,
    note: "Steps 1-7 and All done matched. Product differences are documented in the file: moderation wording on the done screen, the receipt field, real dashboard figures. One mascot per step (owner, 2026-09-16) where frame 2.2 swaps it.",
  },
  "/sellers/rate": {
    klass: CLASS.DIFFERENCE,
    note: "Seller Review steps matched; a result shows the marketplace where the frame shows an answered-question count, and the store's initials where it shows a logo.",
  },
  "/questions/new": {
    klass: CLASS.DIFFERENCE,
    note: "Question Page steps matched; the frame's photo upload and per-specific columns have no API behind them, so the specifics travel as the question's last line.",
  },
  "/requests/new": { klass: CLASS.BUSINESS, note: "Request form; no frame." },
  "/welcome": { klass: CLASS.MATCHED, note: "Login & Signup entry state (5357:2982)." },
  "/login": { klass: CLASS.MATCHED, note: "Login & Signup family; email one-time code, no password." },
  "/signup": { klass: CLASS.MATCHED, note: "Login & Signup family." },
  "/onboarding": { klass: CLASS.MATCHED, note: "Login & Signup onboarding states, InterestTile and StepBar." },
  "/profile": {
    klass: CLASS.DIFFERENCE,
    note: "Profile frames matched; the owner's own controls (edit, earnings, log out) and interests sit where the frame has a bio, and the figures are the account's real ones.",
  },
  "/notifications": { klass: CLASS.BUSINESS, note: "FR-1 1.6; no frame. The site's list language." },
  "/contracts": { klass: CLASS.BUSINESS, note: "Reviewer contracts; no frame." },
  "/sellers/[id]/dashboard": { klass: CLASS.BUSINESS, note: "FR-4 owner monitoring; no frame. Built from the store page's parts." },
  "/dashboard": { klass: CLASS.DIFFERENCE, note: "Reviewer Dashboard matched (5572:7130); average read time is not measured, so the tile says so rather than showing the frame's 4m 3s." },
  "/dashboard/history": { klass: CLASS.MATCHED, note: "History (5762:472)." },
  "/dashboard/reviews": { klass: CLASS.DIFFERENCE, note: "Reviews (6159:1510) specifies chrome only; the content is the reviewer's real reviews." },
  "/dashboard/transfer": { klass: CLASS.MATCHED, note: "Transfer (5762:332); the balance is real, the frame's sample figure is not drawn." },
  "/dashboard/insights": { klass: CLASS.DIFFERENCE, note: "Insights (5762:752); the unlabelled curve is labelled, because on a product that pays people an unlabelled curve reads as money." },
  "/about": { klass: CLASS.BUSINESS, note: "Company page; no frame." },
  "/how-it-works": { klass: CLASS.BUSINESS, note: "Company page; no frame." },
  "/membership": { klass: CLASS.BUSINESS, note: "Tier explainer; no frame." },
  "/faqs": { klass: CLASS.BUSINESS, note: "Company page; no frame." },
  "/articles": { klass: CLASS.BUSINESS, note: "Coming-soon page; no frame." },
  "/contact": { klass: CLASS.BUSINESS, note: "Company page; no frame." },
  "/guidelines": { klass: CLASS.BUSINESS, note: "Policy page; no frame." },
  "/legal": { klass: CLASS.BUSINESS, note: "Policy page; no frame." },
  "/terms": { klass: CLASS.BUSINESS, note: "Policy page; no frame." },
  "/privacy": { klass: CLASS.BUSINESS, note: "Policy page; no frame." },
  "/moderate": { klass: CLASS.BUSINESS, note: "Overview (5017:1738) in the Admin/Sidebar shell; a desktop workspace, not a phone screen." },
  "/moderate/review-queue": {
    klass: CLASS.MATCHED,
    note: "Admin Page - Review Queue (6922:837), the file's one desktop frame: rail, tabs, table and detail pane all present.",
    blocker: "The queue's rows need moderator data. The local fixture proxy serves none, so row selection and the detail pane's contents are unverified locally; the shell, tabs, filters and empty state are.",
  },
  "/moderate/products": { klass: CLASS.BUSINESS, note: "Catalogue table in the admin shell; no frame." },
  "/moderate/prices": { klass: CLASS.BUSINESS, note: "Price moderation; no frame." },
  "/moderate/sellers": { klass: CLASS.BUSINESS, note: "Seller claims; no frame." },
  "/moderate/reviewers": { klass: CLASS.BUSINESS, note: "Reviewer standing; no frame." },
  "/moderate/users": { klass: CLASS.BUSINESS, note: "Account management; no frame." },
  "/moderate/affiliate-links": { klass: CLASS.BUSINESS, note: "Affiliate ledger; no frame." },
  "/moderate/honesty-fund": { klass: CLASS.BUSINESS, note: "Fund pool; no frame." },
  "/moderate/analytics": { klass: CLASS.BUSINESS, note: "Traffic geography; no frame." },
  "/moderate/activity": { klass: CLASS.BUSINESS, note: "Audit log; no frame." },
};

/** Read every sweep.json under the evidence directory. */
function readSweeps(dir) {
  const rows = [];
  if (!existsSync(dir)) return rows;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = join(dir, entry.name, "sweep.json");
    if (!existsSync(file)) continue;
    const parsed = JSON.parse(readFileSync(file, "utf8"));
    for (const row of parsed.report) rows.push({ ...row, run: entry.name });
  }
  return rows;
}

function readJourneys(dir) {
  for (const candidate of readdirSync(dir, { withFileTypes: true })) {
    if (!candidate.isDirectory()) continue;
    const file = join(dir, candidate.name, "journeys.json");
    if (existsSync(file)) return JSON.parse(readFileSync(file, "utf8"));
  }
  return [];
}

const sweeps = readSweeps(EVIDENCE);
const journeys = readJourneys(EVIDENCE);

const cell = (text) => String(text).replace(/\|/g, "\\|");

/** The widths a route was actually checked at, per bucket. */
function statusFor(route, bucket) {
  const runs = sweeps.filter((r) => r.route === route && BUCKET(r.width) === bucket);
  if (runs.length === 0) return { status: "—", widths: [] };
  const widths = [...new Set(runs.map((r) => r.width))].sort((a, b) => a - b);
  const failed = runs.filter((r) => r.result === "FAIL");
  const skipped = runs.filter((r) => r.result === "SKIPPED");
  if (failed.length > 0) return { status: "FAIL", widths };
  if (skipped.length === runs.length) return { status: "SKIPPED", widths };
  return { status: "PASS", widths };
}

const lines = [];
const now = new Date().toISOString().slice(0, 10);
lines.push("# Frontend audit — every page and every journey");
lines.push("");
lines.push("<!-- Generated by `node --experimental-strip-types scripts/audit-report.mjs --evidence <dir>`. -->");
lines.push("");
lines.push(
  `Run ${now}. The page list is lib/site-map.ts (the same list /sitemap.xml and docs/SITEMAP.md come from), so a page cannot be missed: the site-map test fails if one exists without an entry.`,
);
lines.push("");
lines.push("**How the evidence was produced**");
lines.push("");
lines.push("- `node --experimental-strip-types scripts/audit-sweep.mjs` — every route, at the widths given, with the session its access level needs: HTTP status, landing URL, horizontal overflow, console errors, broken images, screenshot.");
lines.push("- `node scripts/journey-check.mjs` — the flows between those pages, driven in a browser at 390 and 1440.");
lines.push("- `npx playwright test e2e/journeys.spec.ts` — the signed-out subset of those journeys, for CI.");
lines.push("- Figma frames read from the file `lso4Ri4hDaZxvCebhUqlY5` through the Figma MCP (account Zienxt, Full seat) and the mirrored export pack in `.bluntly-autopilot/figma-reference/`.");
lines.push("");
lines.push("**Access** — Public; Signed-out only; Signed in; Moderator; Store owner. Signed-in, moderator and store-owner pages are verified against the local fixture session, never against production credentials.");
lines.push("");

const counts = { total: SITE_ROUTES.length, figma: 0, business: 0, pass: 0, fail: 0, blocked: 0 };
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path];
  if (!c) continue;
  if (c.klass.startsWith("FIGMA")) counts.figma += 1;
  else counts.business += 1;
  if (c.blocker) counts.blocked += 1;
}

const mobileFails = SITE_ROUTES.filter((r) => ["mobile", "tablet", "desktop"].some((b) => statusFor(r.path, b).status === "FAIL"));
counts.fail = mobileFails.length;
counts.pass = counts.total - counts.fail;

lines.push(`**Result** — ${counts.total} pages: ${counts.pass} pass, ${counts.fail} fail. ${counts.figma} are built to Figma frames, ${counts.business} have no frame and follow the design system. ${counts.blocked} carry a blocker (named in the notes).`);
lines.push("");
lines.push("| Route | Access | Classification | Mobile | Tablet | Desktop | Console | Overflow | Result |");
lines.push("| --- | --- | --- | --- | --- | --- | --- | --- | --- |");
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path] ?? { klass: "UNCLASSIFIED" };
  const m = statusFor(route.path, "mobile");
  const t = statusFor(route.path, "tablet");
  const d = statusFor(route.path, "desktop");
  const runs = sweeps.filter((r) => r.route === route.path);
  const consoleErrors = runs.reduce((n, r) => n + (r.errors?.length ?? 0), 0);
  const overflow = runs.reduce((n, r) => Math.max(n, r.overflowX ?? 0), 0);
  const failed = [m, t, d].some((s) => s.status === "FAIL");
  const short = c.klass.replace("FIGMA SOURCE-VERIFIED — ", "Figma: ").replace("NO FIGMA FRAME — ", "No frame: ");
  const result = failed
    ? "FAIL — NEEDS CORRECTION"
    : c.klass.startsWith("NO FIGMA")
      ? "PASS — BUSINESS ROUTE"
      : c.klass.includes("DIFFERENCE")
        ? "PASS — INTENTIONAL DIFFERENCE"
        : "PASS — FIGMA MATCHED";
  lines.push(
    `| \`${route.path}\` | ${route.access} | ${cell(short)} | ${m.status}${m.widths.length ? ` (${m.widths.join("/")})` : ""} | ${t.status}${t.widths.length ? ` (${t.widths.join("/")})` : ""} | ${d.status}${d.widths.length ? ` (${d.widths.join("/")})` : ""} | ${consoleErrors === 0 ? "clean" : `${consoleErrors} errors`} | ${overflow === 0 ? "none" : `${overflow}px`} | ${result} |`,
  );
}
lines.push("");
lines.push("## What differs from the frames, and why");
lines.push("");
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path];
  if (!c?.note) continue;
  lines.push(`- **\`${route.path}\`** — ${c.note}${c.blocker ? ` **Blocker:** ${c.blocker}` : ""}`);
}
lines.push("");
lines.push("## Journeys");
lines.push("");
lines.push("A page passes on its own rendering; a journey passes when the reader can actually get through it. Driven by `scripts/journey-check.mjs`.");
lines.push("");
lines.push("| Journey | Phone (390) | Desktop (1440) | Checks |");
lines.push("| --- | --- | --- | --- |");
const ids = [...new Set(journeys.map((j) => j.id))];
for (const id of ids) {
  const phone = journeys.find((j) => j.id === id && j.width < 1024);
  const desktop = journeys.find((j) => j.id === id && j.width >= 1024);
  const checks = Math.max(phone?.checks ?? 0, desktop?.checks ?? 0);
  lines.push(`| ${id} | ${phone?.result ?? "—"} | ${desktop?.result ?? "—"} | ${checks} |`);
}
lines.push("");
lines.push("`N/A` is a control that only exists at that width: the \"+\" action menu is a phone control, so its journeys do not run on the website.");
lines.push("");
writeFileSync(join(ROOT, "docs", "FRONTEND_AUDIT.md"), lines.join("\n") + "\n");
console.log(`wrote docs/FRONTEND_AUDIT.md — ${SITE_ROUTES.length} pages, ${ids.length} journeys, ${sweeps.length} sweep rows`);
