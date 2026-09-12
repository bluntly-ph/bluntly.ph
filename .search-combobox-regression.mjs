import { chromium } from "playwright";

/**
 * Real-browser regression for the search combobox.
 *
 * WHY THIS EXISTS AS A BROWSER TEST.
 *
 * `<input type="search">` clears itself when Escape is pressed. That is a
 * browser default — nothing in the component does it — and it silently
 * contradicted the component's intent: Escape should dismiss the suggestions
 * and KEEP what was typed. Because the query was wiped, there was also nothing
 * left for ArrowDown to reopen.
 *
 * Neither TypeScript nor ESLint can see a missing `preventDefault()`, and a
 * synthetic `dispatchEvent(new KeyboardEvent("keydown"))` does NOT reproduce it
 * either — synthetic events carry no native default action. So the unit tests in
 * tests/frontend/search-combobox-model.test.mjs pin the decision logic, and this
 * file is the only thing that can prove the decision reaches a real browser.
 *
 * Usage:
 *   node .search-combobox-regression.mjs [baseUrl]
 * Defaults to http://localhost:3000; pass https://www.bluntly.ph to verify a
 * deployed candidate. Read-only: it types, presses keys and navigates, and
 * writes nothing.
 */

const BASE = (process.argv[2] || "http://localhost:3000").replace(/\/$/, "");
const QUERY = "iphone";
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 393, height: 850 },
];

const browser = await chromium.launch({
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--renderer-process-limit=4"],
});

let pass = 0;
let fail = 0;
const fails = [];
const check = (name, ok, detail = "") => {
  if (ok) pass++;
  else {
    fail++;
    fails.push(name);
  }
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

const options = (page) => page.locator('[role="option"]');

async function run(viewport, route, label) {
  const ctx = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
  });
  const page = await ctx.newPage();
  const errors = [];
  const failedRequests = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !/eval\(\)/.test(m.text())) errors.push(m.text().slice(0, 110));
  });
  page.on("response", (r) => {
    const u = new URL(r.url());
    if (u.hostname.endsWith("bluntly.ph") && r.status() >= 400) {
      failedRequests.push(`${r.status()} ${u.pathname}`);
    }
  });

  const where = `${label} ${viewport.name}`;
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2600);

  // The VISIBLE COMBOBOX, not merely the first search input in the DOM.
  //
  // Two traps this avoids. The header search is `md:`-gated, so on a phone it is
  // present but hidden, and on /search it precedes the page's own field — so
  // `.first()` grabbed the hidden one and silently skipped the surface under
  // test. And the landing hero is a plain `<input type="search">` GET form with
  // no autocomplete at all, so asserting suggestions against it tested an
  // element that never had them. `role="combobox"` is exactly the set that
  // mounts SearchAutocomplete.
  const box = page.locator('input[role="combobox"]:visible').first();
  if ((await box.count()) === 0) {
    // Genuinely nothing to drive here (the header on a phone, by design).
    console.log(`SKIP  ${where} — no visible combobox on this surface (by design)`);
    await ctx.close();
    return { errors, failedRequests };
  }
  check(`${where} combobox present`, true);

  // The field must remain a real GET form so search works without JavaScript.
  const action = await box.evaluate((el) => el.closest("form")?.getAttribute("action") ?? null);
  check(`${where} is a real GET form (no-JS fallback)`, action === "/search", String(action));

  // --- threshold and empty-input behaviour ---
  await box.click();
  await page.waitForTimeout(800);
  check(`${where} empty focus suggests nothing`, (await options(page).count()) === 0);
  await box.fill(" ");
  await page.waitForTimeout(800);
  check(`${where} whitespace suggests nothing`, (await options(page).count()) === 0);

  const productRequests = [];
  const spy = (r) => {
    if (r.url().includes("/products?q=")) productRequests.push(r.url());
  };
  page.on("request", spy);
  await box.fill(QUERY.slice(0, 1));
  await page.waitForTimeout(1200);
  check(`${where} one character issues no request`, productRequests.length === 0,
    `${productRequests.length} requests`);
  page.off("request", spy);

  // --- suggestions appear for a 2+ character query ---
  await box.fill(QUERY);
  await page.waitForTimeout(1800);
  const shown = await options(page).count();
  check(`${where} 2+ characters show suggestions`, shown > 0, `${shown} options`);
  if (shown === 0) {
    await ctx.close();
    return { errors, failedRequests };
  }

  /* ====================== THE REGRESSION ITSELF ======================= */
  // A real keyboard Escape, through the browser's own default handling.
  await box.press("Escape");
  await page.waitForTimeout(600);
  check(`${where} Escape dismisses the suggestions`, (await options(page).count()) === 0);
  const afterEscape = await box.inputValue();
  check(
    `${where} Escape KEEPS the query (the native type=search clear is suppressed)`,
    afterEscape === QUERY,
    `value is "${afterEscape}", expected "${QUERY}"`,
  );

  // And the retained query is what ArrowDown reopens against.
  await box.press("ArrowDown");
  await page.waitForTimeout(1200);
  const reopened = await options(page).count();
  check(`${where} ArrowDown reopens the list after Escape`, reopened > 0, `${reopened} options`);
  check(`${where} the query is still intact after reopening`,
    (await box.inputValue()) === QUERY, await box.inputValue());

  const activeDesc = await box.getAttribute("aria-activedescendant");
  const selected = await page.locator('[role="option"][aria-selected="true"]').count();
  check(`${where} ArrowDown highlights an option via aria-activedescendant`,
    Boolean(activeDesc) && selected === 1, `activedescendant=${activeDesc}`);
  const focusStaysOnInput = await page.evaluate(
    () => document.activeElement?.getAttribute("type") === "search",
  );
  check(`${where} focus stays on the input (combobox pattern)`, focusStaysOnInput);

  // --- ArrowUp ---
  const first = await box.getAttribute("aria-activedescendant");
  await box.press("ArrowDown");
  await page.waitForTimeout(300);
  const second = await box.getAttribute("aria-activedescendant");
  await box.press("ArrowUp");
  await page.waitForTimeout(300);
  check(`${where} ArrowUp returns to the previous option`,
    second !== first && (await box.getAttribute("aria-activedescendant")) === first,
    `${first} -> ${second} -> back`);

  // --- a second Escape still clears, which is a useful affordance ---
  await box.press("Escape");
  await page.waitForTimeout(400);
  await box.press("Escape");
  await page.waitForTimeout(400);
  check(`${where} a second Escape on a closed list still clears the field`,
    (await box.inputValue()) === "", `value "${await box.inputValue()}"`);

  // --- Enter on a highlighted option searches for it ---
  await box.fill(QUERY);
  await page.waitForTimeout(1800);
  if ((await options(page).count()) > 0) {
    await box.press("ArrowDown");
    await page.waitForTimeout(300);
    await box.press("Enter");
    await page.waitForTimeout(2800);
    check(`${where} Enter on a highlighted option searches for it`,
      /[?&]q=/.test(page.url()), new URL(page.url()).search.slice(0, 46));
  }

  // --- pointer selection ---
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2400);
  const box2 = page.locator('input[role="combobox"]:visible').first();
  await box2.fill(QUERY);
  await page.waitForTimeout(1800);
  if ((await options(page).count()) > 0) {
    const cursor = await options(page).first().evaluate((el) => getComputedStyle(el).cursor);
    check(`${where} options show a pointer cursor`, cursor === "pointer", cursor);
    await options(page).first().click();
    await page.waitForTimeout(2800);
    check(`${where} clicking an option searches for it`,
      /[?&]q=/.test(page.url()), new URL(page.url()).search.slice(0, 46));
  }

  // --- the clear button resets the URL too, not just the field ---
  await page.goto(`${BASE}/search?q=${QUERY}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2600);
  const clear = page.getByRole("button", { name: /Clear search/i });
  if ((await clear.count()) > 0) {
    await clear.click();
    await page.waitForTimeout(2200);
    check(`${where} clear empties the field`,
      (await page.locator('input[role="combobox"]:visible').first().inputValue()) === "");
    check(`${where} clear also resets the query in the URL`,
      !/[?&]q=[^&]+/.test(page.url()), page.url().replace(BASE, ""));
  }

  await ctx.close();
  return { errors, failedRequests };
}

const allErrors = [];
const allFailed = [];
for (const viewport of VIEWPORTS) {
  for (const [route, label] of [["/", "header"], ["/search", "/search"]]) {
    const { errors, failedRequests } = await run(viewport, route, label);
    allErrors.push(...errors);
    allFailed.push(...failedRequests);
  }
}

check("no console errors", allErrors.length === 0, [...new Set(allErrors)].slice(0, 3).join(" | "));
check("no 4xx/5xx from bluntly", allFailed.length === 0, [...new Set(allFailed)].slice(0, 4).join(" | "));

await browser.close();
console.log(`\n${pass}/${pass + fail} checks passed  (${BASE})`);
if (fails.length) {
  console.log(`\nFAILING:\n${fails.map((f) => `  - ${f}`).join("\n")}`);
}
process.exit(fail === 0 ? 0 : 1);
