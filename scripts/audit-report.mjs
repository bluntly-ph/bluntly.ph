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
/**
 * Which journeys exercise which route, so a page's row can say whether its
 * flows were driven, not just whether it rendered.
 */
const JOURNEYS_BY_ROUTE = {
  "/search": [
    "J-SEARCH-REVIEW",
    "J-SEARCH-TABS",
    "J-SEARCH-FILTER",
    "J-SEARCH-SORT",
    "J-SEARCH-FAB-WRITE",
    "J-SEARCH-FAB-ASK",
    "J-PROFILE-MENU",
  ],
  "/reviews/[id]": ["J-SEARCH-REVIEW", "J-REVIEW-ACTIONS"],
  "/questions": ["J-QUESTION-OPEN"],
  "/questions/[id]": ["J-QUESTION-OPEN"],
  "/sellers/[id]": ["J-SELLER-TABS", "J-SELLER-FAB-RATE", "J-SELLER-DASHBOARD"],
  "/sellers/[id]/dashboard": ["J-SELLER-DASHBOARD"],
  "/reviews/new": ["J-COMPOSER-REVIEW", "J-SEARCH-FAB-WRITE", "J-AUTH-RETURN"],
  "/sellers/rate": ["J-COMPOSER-SELLER", "J-SELLER-FAB-RATE"],
  "/questions/new": ["J-COMPOSER-QUESTION", "J-SEARCH-FAB-ASK"],
  "/login": ["J-AUTH-RETURN"],
  "/profile": ["J-PROFILE-MENU"],
  "/dashboard": ["J-PROFILE-MENU", "J-DASHBOARD-NAV"],
  "/dashboard/history": ["J-DASHBOARD-NAV"],
  "/dashboard/transfer": ["J-DASHBOARD-NAV"],
  "/dashboard/insights": ["J-DASHBOARD-NAV"],
  "/moderate": ["J-MODERATE-QUEUE"],
  "/moderate/review-queue": ["J-MODERATE-QUEUE", "J-MODERATE-DETAIL"],
  "/moderate/products": ["J-MODERATE-QUEUE"],
  "/about": ["J-FOOTER-LEGAL"],
  "/privacy": ["J-FOOTER-LEGAL"],
  "/terms": ["J-FOOTER-LEGAL"],
  "/guidelines": ["J-FOOTER-LEGAL"],
};

/**
 * States a route can be in, and whether this audit has evidence for each.
 * Only states actually observed are marked verified — a page passing in its
 * default state says nothing about the others, which is the distinction
 * "49/49 PASS" on its own would hide.
 */
const STATES = {
  "/": [
    ["signed-out landing", "VERIFIED"],
    ["owner Earned badge, 320-1440", "VERIFIED"],
  ],
  "/search": [
    ["results", "VERIFIED"],
    ["tab switch, filter, order", "VERIFIED"],
    ["no results", "NOT EXERCISED"],
  ],
  "/feed": [["for-you and recent", "VERIFIED"]],
  "/compare": [
    ["empty picker", "VERIFIED"],
    ["two to four products compared", "NOT EXERCISED"],
  ],
  "/reviews/[id]": [
    ["published review with comments", "VERIFIED"],
    ["overflow menu open and dismissed", "VERIFIED"],
  ],
  "/sellers/[id]": [
    ["claimed store with reviews", "VERIFIED"],
    ["Questions tab", "VERIFIED"],
    ["store with no reviews", "NOT EXERCISED"],
  ],
  "/u/[id]": [
    ["reviewer with reviews", "VERIFIED"],
    ["loading skeleton", "VERIFIED"],
  ],
  "/questions": [
    ["populated list", "VERIFIED"],
    ["empty list", "NOT EXERCISED"],
  ],
  "/questions/[id]": [
    ["unanswered and answered", "VERIFIED"],
    ["answer posted", "NOT EXERCISED — writes"],
  ],
  "/requests": [["populated board", "VERIFIED"]],
  "/reviews/new": [
    ["product picker, steps 1-4, walk back", "VERIFIED"],
    ["steps 5-7 and All done", "VERIFIED IN THE 2026-09-16 COMPOSER PASS"],
    ["submission", "NOT EXERCISED — writes"],
  ],
  "/sellers/rate": [
    ["find, rate, write-up", "VERIFIED"],
    ["submission", "NOT EXERCISED — writes"],
  ],
  "/questions/new": [
    ["audience, product, question gate", "VERIFIED"],
    ["submission", "NOT EXERCISED — writes"],
  ],
  "/login": [
    ["form and return path", "VERIFIED"],
    ["one-time code step", "NOT EXERCISED — needs mail"],
  ],
  "/profile": [
    ["own profile, no reviews yet", "VERIFIED"],
    ["profile with reviews", "VERIFIED VIA /u/[id]"],
  ],
  "/notifications": [
    ["unreachable-API state", "VERIFIED"],
    ["populated list", "NOT EXERCISED — no fixture"],
  ],
  "/contracts": [
    ["empty state", "VERIFIED"],
    ["with contracts", "NOT EXERCISED — no fixture"],
  ],
  "/sellers/[id]/dashboard": [
    ["owner view with months and waiting questions", "VERIFIED"],
    ["non-owner message", "NOT EXERCISED"],
  ],
  "/dashboard": [
    ["zero-earnings state", "VERIFIED"],
    ["with earnings", "NOT EXERCISED — no fixture"],
  ],
  "/dashboard/history": [["empty history", "VERIFIED"]],
  "/dashboard/reviews": [["no published reviews", "VERIFIED"]],
  "/dashboard/transfer": [
    ["below payout threshold", "VERIFIED"],
    ["withdrawal request", "NOT EXERCISED — writes"],
  ],
  "/dashboard/insights": [["no data yet", "VERIFIED"]],
  "/moderate": [
    ["overview shell", "VERIFIED"],
    ["populated overview", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/review-queue": [
    ["shell, tabs, filters, empty state", "VERIFIED"],
    ["populated queue and detail pane", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/products": [["populated catalogue", "VERIFIED"]],
  "/moderate/prices": [
    ["shell and unreachable-API state", "VERIFIED"],
    ["pending observations", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/sellers": [
    ["shell and unreachable-API state", "VERIFIED"],
    ["pending claims", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/reviewers": [
    ["shell and unreachable-API state", "VERIFIED"],
    ["populated table", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/users": [
    ["search shell", "VERIFIED"],
    ["a found account", "BLOCKED — no moderator fixture data"],
  ],
  "/moderate/affiliate-links": [["shell and empty ledger", "VERIFIED"]],
  "/moderate/honesty-fund": [["current cycle, zero pool", "VERIFIED"]],
  "/moderate/analytics": [["shell and distribution panel", "VERIFIED"]],
  "/moderate/activity": [
    ["shell and unreachable-API state", "VERIFIED"],
    ["populated log", "BLOCKED — no moderator fixture data"],
  ],
};

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
  "/sellers/[id]/dashboard": {
    klass: CLASS.BUSINESS,
    note: "FR-4 owner monitoring; no frame. Built from the store page's parts.",
  },
  "/dashboard": {
    klass: CLASS.DIFFERENCE,
    note: "Reviewer Dashboard matched (5572:7130); average read time is not measured, so the tile says so rather than showing the frame's 4m 3s.",
  },
  "/dashboard/history": { klass: CLASS.MATCHED, note: "History (5762:472)." },
  "/dashboard/reviews": {
    klass: CLASS.DIFFERENCE,
    note: "Reviews (6159:1510) specifies chrome only; the content is the reviewer's real reviews.",
  },
  "/dashboard/transfer": {
    klass: CLASS.MATCHED,
    note: "Transfer (5762:332); the balance is real, the frame's sample figure is not drawn.",
  },
  "/dashboard/insights": {
    klass: CLASS.DIFFERENCE,
    note: "Insights (5762:752); the unlabelled curve is labelled, because on a product that pays people an unlabelled curve reads as money.",
  },
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
  "/moderate": {
    klass: CLASS.BUSINESS,
    note: "Overview (5017:1738) in the Admin/Sidebar shell; a desktop workspace, not a phone screen.",
  },
  "/moderate/review-queue": {
    klass: CLASS.MATCHED,
    note: "Admin Page - Review Queue (6922:837), the file's one desktop frame: rail, tabs, table and detail pane all present.",
    blocker:
      "The queue's rows need moderator data. The local fixture proxy serves none, so row selection and the detail pane's contents are unverified locally; the shell, tabs, filters and empty state are.",
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

/** Evidence limits that are not any one route's failure. */
const LIMITATIONS = [
  [
    "Review queue with rows",
    "CLOSED",
    "Was blocked. Deterministic local fixture cards now populate GET /admin/review-queue, so the rows, row selection and the detail pane are verified at 390, 768, 1024 and 1440 — no overflow, no console errors.",
  ],
  [
    "The other moderator queues with data",
    "BLOCKED",
    "Prices, seller claims, reviewers, users and the activity log still have no local payloads, so their populated tables have no evidence. Their shells and unreachable-API states do. Closing it needs fixtures per endpoint or a signed-in moderator on a real stack.",
  ],
  [
    "Moderator decisions",
    "NOT AVAILABLE IN THE PRODUCT",
    "There is no approve/reject/publish control on the review queue, and the Figma frame draws none. The API has the endpoints and an unmounted component calls them. A product decision for the owner, recorded here rather than built during the freeze.",
  ],
  [
    "Authenticated routes on production",
    "HUMAN_AUTH_REQUIRED",
    "Every signed-in, store-owner and moderator route here is LOCAL FIXTURE VERIFIED. Production sign-in is an emailed one-time code, so live authenticated verification belongs to the owner or independent QA.",
  ],
  [
    "Seller-dependent routes on production",
    "NOT LIVE-DATA VERIFIED",
    "Production holds no seller record, so /sellers/[id] and its dashboard cannot be opened live. Local fixture evidence stands; this is an evidence limitation, not a frontend failure.",
  ],
  [
    "Anything that writes",
    "NOT EXERCISED",
    "Review, seller-review and question submission, answering, voting and withdrawal are not driven against a real API: the audit answers those POSTs in the browser. Everything up to the submit control is verified.",
  ],
  [
    "The one-time-code step",
    "NOT EXERCISED",
    "Login past the email step needs a mail hook. The form, its validation and the return path are verified.",
  ],
];

lines.push("# Frontend audit — pages, journeys, states and evidence limits");
lines.push("");
lines.push("<!-- Generated by `node --experimental-strip-types scripts/audit-report.mjs --evidence <dir>`. -->");
lines.push("");
lines.push(
  `Run ${now}. The page list is lib/site-map.ts — the same list /sitemap.xml and docs/SITEMAP.md come from — so a page cannot be missed: the site-map test fails if one exists without an entry.`,
);
lines.push("");
lines.push(
  "**Read this as four separate claims.** A page can render correctly in its default state while a state inside it has no evidence at all, so a page result never stands in for state coverage.",
);
lines.push("");
lines.push("| Claim | What it means |");
lines.push("| --- | --- |");
lines.push(
  "| Page result | The route rendered at every width checked: right status, no redirect away from it, no horizontal overflow, no console errors, no broken images. |",
);
lines.push("| Journey result | The flows through that route were driven in a browser and landed where they should. |");
lines.push(
  "| State coverage | Which of the route's states this audit actually put on screen. A state not listed as verified was not seen. |",
);
lines.push("| Evidence limitations | What could not be verified at all, and why. |");
lines.push("");
lines.push("**How the evidence was produced**");
lines.push("");
lines.push(
  "- `node --experimental-strip-types scripts/audit-sweep.mjs` — every route, at the widths given, with the session its access level needs: HTTP status, the URL it actually landed on, horizontal overflow, console errors, broken images, screenshot.",
);
lines.push("- `node scripts/journey-check.mjs` — the flows between those pages, driven at 390 and 1440.");
lines.push("- `npx playwright test e2e/journeys.spec.ts` — the signed-out subset, for CI.");
lines.push(
  "- Figma frames read from file `lso4Ri4hDaZxvCebhUqlY5` through the Figma MCP (account Zienxt, Full seat) and the mirrored export pack in `.bluntly-autopilot/figma-reference/`.",
);
lines.push("");
lines.push("Engineering verification is not an independent QA pass. **Independent QA: RETEST REQUIRED.**");
lines.push("");

const pageResult = (route) => {
  const buckets = ["mobile", "tablet", "desktop"].map((b) => statusFor(route, b));
  if (buckets.some((b) => b.status === "FAIL")) return "FAIL";
  if (buckets.every((b) => b.status === "SKIPPED" || b.status === "—")) return "NOT VERIFIED";
  if (buckets.some((b) => b.status === "SKIPPED")) return "PARTIAL";
  return "PASS";
};

const journeyResult = (route) => {
  const ids = JOURNEYS_BY_ROUTE[route] ?? [];
  const runs = journeys.filter((j) => ids.includes(j.id) && j.result !== "N/A");
  if (runs.length === 0) return "no journey";
  if (runs.some((j) => j.result === "FAIL")) return "FAIL";
  return `PASS (${ids.length})`;
};

const counts = { figma: 0, business: 0, pass: 0, fail: 0, partial: 0, notVerified: 0, stateGaps: 0 };
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path];
  if (c?.klass?.startsWith("FIGMA")) counts.figma += 1;
  else counts.business += 1;
  const r = pageResult(route.path);
  if (r === "PASS") counts.pass += 1;
  else if (r === "FAIL") counts.fail += 1;
  else if (r === "PARTIAL") counts.partial += 1;
  else counts.notVerified += 1;
  const states = STATES[route.path] ?? [];
  if (states.some(([, status]) => status.startsWith("BLOCKED") || status.startsWith("NOT EXERCISED"))) {
    counts.stateGaps += 1;
  }
}
const journeyIds = [...new Set(journeys.map((j) => j.id))];
const journeyFails = journeys.filter((j) => j.result === "FAIL").length;

lines.push("## Summary");
lines.push("");
lines.push(
  `- **Pages** — ${SITE_ROUTES.length} routes: ${counts.pass} PASS, ${counts.partial} PARTIAL, ${counts.notVerified} NOT VERIFIED, ${counts.fail} FAIL. ${counts.figma} are built to Figma frames; ${counts.business} have no frame and follow the design system.`,
);
lines.push(
  `- **Journeys** — ${journeyIds.length} journeys, ${journeys.length} runs across 390 and 1440, ${journeyFails} failing.`,
);
lines.push(
  `- **State coverage** — ${counts.stateGaps} routes carry at least one state with no evidence. Those are listed in section 3; a PASS above does not cover them.`,
);
lines.push(`- **Evidence limitations** — ${LIMITATIONS.length}, in section 4.`);
lines.push("");

lines.push("## 1. Page results");
lines.push("");
lines.push(
  "| Route | Access | Classification | Mobile | Tablet | Desktop | Console | Overflow | Page result | Journeys |",
);
lines.push("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |");
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path] ?? { klass: "UNCLASSIFIED" };
  const [m, t, d] = ["mobile", "tablet", "desktop"].map((b) => statusFor(route.path, b));
  const runs = sweeps.filter((r) => r.route === route.path);
  const consoleErrors = runs.reduce((n, r) => n + (r.errors?.length ?? 0), 0);
  const overflow = runs.reduce((n, r) => Math.max(n, r.overflowX ?? 0), 0);
  const short = c.klass.replace("FIGMA SOURCE-VERIFIED — ", "Figma: ").replace("NO FIGMA FRAME — ", "No frame: ");
  const widths = (x) => (x.widths.length ? `${x.status} (${x.widths.join("/")})` : x.status);
  lines.push(
    `| \`${route.path}\` | ${route.access} | ${cell(short)} | ${widths(m)} | ${widths(t)} | ${widths(d)} | ${
      consoleErrors === 0 ? "clean" : `${consoleErrors} errors`
    } | ${overflow === 0 ? "none" : `${overflow}px`} | ${pageResult(route.path)} | ${journeyResult(route.path)} |`,
  );
}
lines.push("");

lines.push("## 2. Journey results");
lines.push("");
lines.push("| Journey | Phone (390) | Desktop (1440) | Assertions |");
lines.push("| --- | --- | --- | --- |");
for (const id of journeyIds) {
  const phone = journeys.find((j) => j.id === id && j.width < 1024);
  const desktop = journeys.find((j) => j.id === id && j.width >= 1024);
  const checks = Math.max(phone?.checks ?? 0, desktop?.checks ?? 0);
  lines.push(`| ${id} | ${phone?.result ?? "—"} | ${desktop?.result ?? "—"} | ${checks} |`);
}
lines.push("");
lines.push(
  'N/A marks a control that only exists at that width: the "+" action menu is a phone control, so its journeys do not run on the website.',
);
lines.push("");

lines.push("## 3. State coverage");
lines.push("");
lines.push("What this audit put on screen, route by route. A state that is not listed was not exercised.");
lines.push("");
for (const route of SITE_ROUTES) {
  const states = STATES[route.path];
  if (!states) continue;
  lines.push(`- **\`${route.path}\`** — ${states.map(([what, status]) => `${what}: ${status}`).join("; ")}`);
}
lines.push("");

lines.push("## 4. Evidence limitations");
lines.push("");
lines.push("| Limitation | Status | Why |");
lines.push("| --- | --- | --- |");
for (const [what, status, why] of LIMITATIONS) lines.push(`| ${cell(what)} | ${status} | ${cell(why)} |`);
lines.push("");

lines.push("## 5. What differs from the frames, and why");
lines.push("");
for (const route of SITE_ROUTES) {
  const c = CLASSIFICATION[route.path];
  if (!c?.note) continue;
  lines.push(`- **\`${route.path}\`** — ${c.note}${c.blocker ? ` **Blocker:** ${c.blocker}` : ""}`);
}
lines.push("");
writeFileSync(join(ROOT, "docs", "FRONTEND_AUDIT.md"), lines.join("\n") + "\n");
console.log(
  `wrote docs/FRONTEND_AUDIT.md — ${SITE_ROUTES.length} pages (${counts.pass} pass, ${counts.partial} partial, ${counts.notVerified} not verified, ${counts.fail} fail), ${journeyIds.length} journeys, ${sweeps.length} sweep rows`,
);
