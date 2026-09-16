/**
 * The journey sweep: the flows that connect the sitemap's pages, driven in a
 * real browser at a phone width and a desktop width.
 *
 *   node --experimental-strip-types scripts/journey-check.mjs
 *   ONLY=J-SEARCH-REVIEW WIDTHS=390 node --experimental-strip-types scripts/journey-check.mjs
 *
 * A page rendering correctly is not the same as its journey working: the
 * composer's Continue, the "+" menu's destinations, a filter that has to change
 * the results, the login return path. Each journey starts where a reader
 * starts, clicks what they would click, and asserts where they land.
 *
 * Signed-in journeys use the local fixture session (the scratch proxy's cookie,
 * never a real credential) and answer the composers' POSTs in the browser, so
 * nothing is written anywhere.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://localhost:3000";
const WIDTHS = (process.env.WIDTHS ?? "390,1440").split(",").map(Number);
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
const OUT = process.env.OUT ?? "journey-out";
const SESSION = { user: "qa-local-fixture", moderator: "qa-local-moderator" };
/** The local fixture store. Override when a different data set is in front. */
const FIXTURE_SELLER = process.env.SELLER_ID ?? "5e11e700-0000-4000-8000-000000000001";
const REVIEW_LINK = "a[href^='/reviews/']:not([href='/reviews/new'])";
const QUESTION_LINK = "a[href^='/questions/']:not([href='/questions/new'])";

mkdirSync(OUT, { recursive: true });

const isPhone = (width) => width < 1024;

/** The "+" action menu is a phone control. */
async function openActionMenu(page) {
  await page.getByRole("button", { name: "Actions", exact: true }).last().click();
  await page.waitForTimeout(300);
}

const JOURNEYS = [
  {
    id: "J-SEARCH-REVIEW",
    entry: "/search",
    auth: null,
    async run(page, expect) {
      const href = await page.locator(REVIEW_LINK).first().getAttribute("href");
      expect(href, "a review card links somewhere");
      await page.locator(`a[href='${href}']`).first().click();
      await page.waitForURL(`**${href}`);
      await page.locator("h1").first().waitFor({ state: "visible", timeout: 20000 });
      expect(true, "the review opens with its headline");
      await page.goBack();
      await page.waitForURL("**/search**");
      expect(page.url().includes("/search"), "back returns to the results");
    },
  },
  {
    id: "J-SEARCH-TABS",
    entry: "/search?q=fan",
    auth: null,
    async run(page, expect) {
      await page.getByRole("link", { name: "Questions", exact: true }).click();
      await page.waitForURL("**tab=questions**");
      await page.getByRole("link", { name: "Sellers", exact: true }).click();
      await page.waitForURL("**tab=sellers**");
      expect(page.url().includes("q=fan"), "the query survives a tab change");
    },
  },
  {
    id: "J-SEARCH-FILTER",
    entry: "/search",
    auth: null,
    async run(page, expect, { width }) {
      if (isPhone(width)) {
        await page.getByRole("button", { name: "All filters" }).click();
        const sheet = page.getByRole("dialog", { name: "All filters" });
        await sheet.waitFor();
        // The radio itself is sr-only behind its drawn ring, so the row is clicked.
        await sheet.getByText("Gaming", { exact: true }).click();
        await sheet.getByRole("button", { name: /Filter Reviews/i }).click();
      } else {
        await page.getByRole("link", { name: "Gaming", exact: true }).click();
      }
      await page.waitForURL("**category=gaming**");
      expect(page.url().includes("category=gaming"), "the category reaches the URL");
    },
  },
  {
    id: "J-SEARCH-SORT",
    entry: "/search",
    auth: null,
    async run(page, expect, { width }) {
      if (isPhone(width)) {
        await page.getByRole("button", { name: "Sort" }).click();
        const sheet = page.getByRole("dialog", { name: "Sort" });
        await sheet.waitFor();
        await sheet.getByText("Latest", { exact: true }).click();
        await sheet.getByRole("button", { name: /Sort|Apply/i }).last().click();
      } else {
        await page.getByRole("link", { name: "Latest", exact: true }).click();
      }
      await page.waitForURL("**sort=newest**");
      expect(page.url().includes("sort=newest"), "the order reaches the URL");
    },
  },
  {
    id: "J-SEARCH-FAB-WRITE",
    entry: "/search",
    auth: "user",
    phoneOnly: true,
    async run(page, expect) {
      await openActionMenu(page);
      await page.getByRole("link", { name: /Write a review/i }).click();
      await page.waitForURL("**/reviews/new");
      expect(true, "the + menu opens the review composer");
    },
  },
  {
    id: "J-SEARCH-FAB-ASK",
    entry: "/search",
    auth: "user",
    phoneOnly: true,
    async run(page, expect) {
      await openActionMenu(page);
      await page.getByRole("link", { name: /Ask a question/i }).click();
      await page.waitForURL("**/questions/new");
      expect(true, "the + menu opens the question composer");
    },
  },
  {
    id: "J-SELLER-FAB-RATE",
    entry: `/sellers/${FIXTURE_SELLER}`,
    auth: "user",
    phoneOnly: true,
    async run(page, expect) {
      await openActionMenu(page);
      await page.getByRole("link", { name: /Rate a Seller/i }).click();
      await page.waitForURL("**/sellers/rate**");
      expect(page.url().includes(FIXTURE_SELLER), "the store travels into the composer");
    },
  },
  {
    id: "J-SELLER-TABS",
    entry: `/sellers/${FIXTURE_SELLER}`,
    auth: null,
    async run(page, expect) {
      await page.getByRole("tab", { name: /Questions/i }).click();
      await page.waitForTimeout(400);
      const selected = await page.getByRole("tab", { name: /Questions/i }).getAttribute("aria-selected");
      expect(selected === "true", "the Questions tab takes over");
      await page.getByRole("tab", { name: /Reviews/i }).first().click();
      await page.waitForTimeout(300);
    },
  },
  {
    id: "J-SELLER-DASHBOARD",
    entry: `/sellers/${FIXTURE_SELLER}`,
    auth: "user",
    async run(page, expect) {
      await page.getByRole("link", { name: /Store dashboard/i }).click();
      await page.waitForURL(`**/sellers/${FIXTURE_SELLER}/dashboard`);
      const heading = page.getByRole("heading", { name: /QA Fixture Store/i }).first();
      expect(await heading.isVisible(), "the owner sees the store's figures");
    },
  },
  {
    id: "J-QUESTION-OPEN",
    entry: "/questions",
    auth: "user",
    async run(page, expect) {
      const href = await page.locator(QUESTION_LINK).first().getAttribute("href");
      expect(href, "a question row links somewhere");
      await page.locator(`a[href='${href}']`).first().click();
      await page.waitForURL(`**${href}`);
      await page.getByRole("heading", { level: 1 }).waitFor({ state: "visible", timeout: 20000 });
      expect(true, "the question opens");
      const answer = page.getByRole("textbox").first();
      await answer.waitFor({ state: "visible", timeout: 20000 });
      expect(true, "a signed-in reader can answer it");
    },
  },
  {
    id: "J-REVIEW-ACTIONS",
    entry: "/search",
    auth: "user",
    async run(page, expect) {
      const href = await page.locator(REVIEW_LINK).first().getAttribute("href");
      await page.goto(BASE + href, { waitUntil: "load" });
      await page.getByRole("button", { name: /More options/i }).first().click();
      await page.waitForTimeout(300);
      expect(await page.getByRole("menu").first().isVisible(), "the overflow menu opens");
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
      expect((await page.getByRole("menu").count()) === 0, "Escape closes it again");
    },
  },
  {
    id: "J-COMPOSER-REVIEW",
    entry: "/reviews/new",
    auth: "user",
    async run(page, expect) {
      await page.getByRole("textbox", { name: /Search for the product/i }).fill("jisulife");
      await page.waitForTimeout(2500);
      await page.locator("main button, main a").filter({ hasText: /Jisulife/i }).first().click();
      await page.waitForTimeout(700);
      expect(await page.getByText("Step 1 out of 7").isVisible(), "picking a product starts step 1");
      const next = () => page.getByRole("button", { name: /Continue/i }).last();
      expect(await next().isDisabled(), "Continue waits for the review to be written");
      await page
        .getByRole("textbox", { name: /experience/i })
        .fill("Fixture text for the journey check. It moves air well and fits in a pocket easily.");
      await page.waitForTimeout(300);
      expect(!(await next().isDisabled()), "Continue opens once the step is satisfied");
      await next().click();
      await page.waitForTimeout(500);
      expect(await page.getByText("Step 2 out of 7").isVisible(), "Continue advances to step 2");
      await page.getByRole("button", { name: /Yes, absolutely/i }).click();
      await page.waitForTimeout(200);
      await next().click();
      await page.waitForTimeout(500);
      expect(await page.getByText("Step 3 out of 7").isVisible(), "a verdict advances to the rating");
      await page.getByRole("button", { name: "4 stars" }).click();
      await page.waitForTimeout(200);
      await next().click();
      await page.waitForTimeout(500);
      expect(await page.getByText("Step 4 out of 7").isVisible(), "a rating advances to pros and cons");
      await page.getByRole("button", { name: /Back to Star rating/i }).click();
      await page.waitForTimeout(500);
      expect(await page.getByText("Step 3 out of 7").isVisible(), "the header arrow walks back a step");
      const pressed = await page.getByRole("button", { name: "4 stars" }).getAttribute("aria-pressed");
      expect(pressed === "true", "the rating survives the walk back");
    },
  },
  {
    id: "J-COMPOSER-SELLER",
    entry: "/sellers/rate",
    auth: "user",
    async run(page, expect) {
      await page.getByLabel("Store name").fill("qa");
      await page.waitForTimeout(2200);
      await page.getByRole("button", { name: /QA Fixture Store/i }).first().click();
      await page.waitForTimeout(700);
      const heading = page.getByRole("heading", { name: /How was the seller/i });
      expect(await heading.isVisible(), "picking a store starts the rating");
      const next = () => page.getByRole("button", { name: /Continue/i }).last();
      expect(await next().isDisabled(), "Continue waits for every dimension");
      await page.getByRole("button", { name: "4 stars" }).click();
      await page.getByRole("button", { name: /I recommend this seller/i }).click();
      for (const dimension of [/Customer Service Responsiveness/i, /Packaging Quality/i]) {
        await page.getByRole("group", { name: dimension }).getByRole("button", { name: "4" }).click();
      }
      await page.getByRole("button", { name: /Yes, accurate/i }).click();
      await page.getByRole("button", { name: /Exact order/i }).click();
      await page.waitForTimeout(400);
      expect(!(await next().isDisabled()), "a complete rating opens Continue");
      await next().click();
      await page.waitForTimeout(600);
      expect(await page.getByText(/Make it pop/i).isVisible(), "Continue reaches the write-up step");
    },
  },
  {
    id: "J-COMPOSER-QUESTION",
    entry: "/questions/new",
    auth: "user",
    async run(page, expect) {
      await page.getByRole("button", { name: /I want to ask other buyers/i }).click();
      await page.waitForTimeout(400);
      await page.getByRole("textbox", { name: /Search for the product/i }).fill("jisulife");
      await page.waitForTimeout(2500);
      await page.locator("main button, main a").filter({ hasText: /Jisulife/i }).first().click();
      await page.waitForTimeout(700);
      const submit = () => page.getByRole("button", { name: /Submit/i }).last();
      expect(await submit().isDisabled(), "Submit waits for a question");
      await page
        .getByRole("textbox", { name: /main question/i })
        .fill("Fixture question for the journey check: how loud is it on the highest speed?");
      await page.waitForTimeout(400);
      expect(!(await submit().isDisabled()), "a written question opens Submit");
    },
  },
  {
    id: "J-AUTH-RETURN",
    entry: "/reviews/new",
    auth: null,
    async run(page, expect) {
      await page.waitForURL("**/login**");
      const next = new URL(page.url()).searchParams.get("next");
      expect(next === "/reviews/new", "the guard keeps where the reader was going");
      expect(await page.getByPlaceholder("Email address").isVisible(), "the login form is ready");
    },
  },
  {
    id: "J-PROFILE-MENU",
    entry: "/search",
    auth: "user",
    async run(page, expect, { width }) {
      if (isPhone(width)) {
        await page.getByRole("button", { name: /Menu and profile/i }).first().click();
        const panel = page.getByRole("dialog", { name: "Navigation and profile" });
        await panel.waitFor();
        await panel.getByRole("link", { name: "Dashboard", exact: true }).click();
      } else {
        await page.goto(`${BASE}/profile`, { waitUntil: "load" });
        await page.getByRole("link", { name: /Earnings/i }).first().click();
      }
      await page.waitForURL("**/dashboard**");
      expect(true, "the account menu reaches the dashboard");
    },
  },
  {
    id: "J-DASHBOARD-NAV",
    entry: "/dashboard",
    auth: "user",
    async run(page, expect) {
      const stops = [
        ["Transfer", "/dashboard/transfer"],
        ["History", "/dashboard/history"],
        ["Insights", "/dashboard/insights"],
      ];
      for (const [label, path] of stops) {
        await page.goto(`${BASE}/dashboard`, { waitUntil: "load" });
        await page.getByRole("link", { name: label, exact: true }).first().click();
        await page.waitForURL(`**${path}`);
        expect(true, `the action bar reaches ${label}`);
      }
    },
  },
  {
    id: "J-MODERATE-QUEUE",
    entry: "/moderate",
    auth: "moderator",
    async run(page, expect, { width }) {
      // Below lg the rail is a drawer. Its button sits bottom-left, where the
      // dev server also parks its indicator, so it is opened directly.
      // Below lg the rail is a drawer, and its closed markup stays in the DOM,
      // so every step here works on what is actually visible. The drawer button
      // is dispatched rather than clicked: the dev server's indicator parks on
      // top of it at bottom-left.
      const openRail = async () => {
        if (!isPhone(width)) return;
        await page.getByRole("button", { name: /Open admin navigation/i }).dispatchEvent("click");
        await page.waitForTimeout(500);
      };
      const railLink = (name) => page.getByRole("link", { name }).filter({ visible: true }).first();
      await openRail();
      await railLink(/Review Queue/i).click();
      await page.waitForURL("**/moderate/review-queue**");
      const heading = page.getByRole("heading", { name: /Review Queue/i }).first();
      expect(await heading.isVisible(), "the queue opens from the rail");
      await openRail();
      await railLink(/Products/i).click();
      await page.waitForURL("**/moderate/products**");
      expect(true, "the rail moves between workspaces");
    },
  },
  {
    id: "J-MODERATE-DETAIL",
    entry: "/moderate/review-queue",
    auth: "moderator",
    async run(page, expect) {
      const rows = page.locator("tbody tr");
      const count = await rows.count();
      // No rows is a data state, not a pass: say so rather than sliding past.
      expect(count > 0, `the queue has rows to inspect (found ${count})`);
      await rows.first().click();
      await page.waitForTimeout(800);
      const body = await page.evaluate(() => document.body.innerText);
      expect(/Trust (Score|stage)/i.test(body), "the detail pane names the author's standing");
      expect(/Receipt/i.test(body), "the detail pane says whether proof of purchase is attached");
      const openFull = page.getByRole("link", { name: /Open the full review/i }).first();
      expect(await openFull.isVisible(), "the pane offers the full review");
      const overflow = await page.evaluate(
        () => document.scrollingElement.scrollWidth - window.innerWidth,
      );
      expect(overflow === 0, "the workspace does not scroll sideways with a card open");
    },
  },
  {
    id: "J-FOOTER-LEGAL",
    entry: "/about",
    auth: null,
    async run(page, expect) {
      for (const name of ["Privacy Policy", "Terms & Conditions", "Community Guidelines"]) {
        const link = page.getByRole("link", { name, exact: true }).first();
        const href = await link.getAttribute("href");
        const res = await page.request.get(BASE + href);
        expect(res.status() === 200, `${name} resolves (${href})`);
      }
    },
  },
];

const browser = await chromium.launch({ args: ["--disable-gpu"] });
const rows = [];
for (const width of WIDTHS) {
  for (const journey of JOURNEYS) {
    if (ONLY.length > 0 && !ONLY.includes(journey.id)) continue;
    if (journey.phoneOnly && !isPhone(width)) {
      rows.push({ id: journey.id, width, result: "N/A", note: "phone-only control" });
      continue;
    }
    const context = await browser.newContext({
      viewport: { width, height: isPhone(width) ? 844 : 900 },
      deviceScaleFactor: 1,
    });
    if (journey.auth) {
      await context.addCookies([
        { name: "bluntly_session", value: SESSION[journey.auth], domain: "localhost", path: "/" },
      ]);
    }
    const page = await context.newPage();
    const checks = [];
    const expect = (value, what) => {
      checks.push({ what, ok: Boolean(value) });
      if (!value) throw new Error(`expected: ${what}`);
    };
    let row;
    try {
      const stub = (route, body) =>
        route.request().method() === "POST"
          ? route.fulfill({ status: 201, contentType: "application/json", body })
          : route.continue();
      await page.route("**/api/bff/api/v1/reviews", (r) => stub(r, JSON.stringify({ id: "journey-fixture" })));
      await page.route("**/api/bff/api/v1/questions", (r) => stub(r, JSON.stringify({ id: "journey-fixture" })));
      await page.goto(BASE + journey.entry, { waitUntil: "load", timeout: 60000 });
      await page.waitForTimeout(600);
      await journey.run(page, expect, { width });
      row = { id: journey.id, width, result: "PASS", checks: checks.length };
    } catch (e) {
      await page.screenshot({ path: join(OUT, `${journey.id}-w${width}.png`) }).catch(() => {});
      row = {
        id: journey.id,
        width,
        result: "FAIL",
        checks: checks.length,
        failed: checks.find((c) => !c.ok)?.what,
        note: String(e.message).split("\n")[0].slice(0, 150),
      };
    }
    rows.push(row);
    const label = row.result === "PASS" ? `ok   (${row.checks} checks)` : `${row.result} — ${row.failed ?? row.note}`;
    console.log(`w${width} ${journey.id}: ${label}`);
    await context.close();
  }
}
await browser.close();
writeFileSync(join(OUT, "journeys.json"), JSON.stringify(rows, null, 1));
const bad = rows.filter((r) => r.result === "FAIL");
console.log(`\n${rows.length} journey runs, ${bad.length} failing`);
for (const b of bad) console.log(`  FAIL w${b.width} ${b.id}: ${b.failed ?? b.note}`);
