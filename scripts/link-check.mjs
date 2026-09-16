#!/usr/bin/env node
/**
 * Does ordinary page loading request anything that 404s? (BUG-029)
 *
 * QA reported "multiple fetch requests return 404 during page load" with the
 * network panel open, cache disabled and 3G throttling on. Two things can cause
 * that, and they need telling apart, because only one is a defect:
 *
 *   a link to a route that does not exist   — a defect. Next prefetches every
 *                                             <Link> in the viewport, so a
 *                                             wrong href becomes a failed
 *                                             request without anyone clicking.
 *   a chunk from a previous deployment      — not a defect. A page held open
 *                                             across a deploy asks for assets
 *                                             the new build does not have. It
 *                                             resolves on reload and no code
 *                                             change can prevent it.
 *
 * This checks the first, and checks the second is not currently happening: it
 * reads each page's rendered HTML, then asks for every internal link and every
 * `/_next` asset that page references.
 *
 *   node scripts/link-check.mjs                      # production, default pages
 *   node scripts/link-check.mjs http://localhost:3000
 *   node scripts/link-check.mjs https://www.bluntly.ph / /search /requests
 *
 * Exit code 1 if anything 404s, so it can gate a release.
 *
 * SIGNED OUT, deliberately: it takes no session and creates none. A redirect to
 * /login is the correct answer for a guarded route and is reported as such, not
 * as a failure — an auth redirect is not this bug.
 */

const DEFAULT_PAGES = ["/", "/search", "/requests", "/categories", "/questions", "/feed"];

const args = process.argv.slice(2);
const base = (args[0] ?? "https://www.bluntly.ph").replace(/\/$/, "");
const pages = args.length > 1 ? args.slice(1) : DEFAULT_PAGES;

/** One request per URL, whatever asks for it. */
const cache = new Map();

async function statusOf(url) {
  if (cache.has(url)) return cache.get(url);
  let result;
  try {
    const res = await fetch(url, { redirect: "manual" });
    result = res.status;
  } catch (error) {
    result = `ERR ${error instanceof Error ? error.message : error}`;
  }
  cache.set(url, result);
  return result;
}

function internalLinks(html) {
  return new Set(
    [...html.matchAll(/href="(\/[^"]*)"/g)]
      .map((m) => m[1])
      .filter((href) => !href.startsWith("//") && !href.startsWith("/_next"))
      .map((href) => href.split("#")[0])
      .filter(Boolean),
  );
}

function staticAssets(html) {
  return new Set([
    ...[...html.matchAll(/"(\/_next\/[^"]+\.(?:js|css))"/g)].map((m) => m[1]),
    ...[...html.matchAll(/src="(\/_next\/[^"]+)"/g)].map((m) => m[1]),
  ]);
}

async function main() {
  console.log(`link-check — ${base}\n`);
  const failures = [];
  const redirects = [];

  for (const page of pages) {
    const res = await fetch(`${base}${page}`);
    const html = await res.text();
    const links = internalLinks(html);
    const assets = staticAssets(html);

    for (const href of links) {
      const status = await statusOf(`${base}${href}`);
      if (status === 404) failures.push({ page, target: href, status, kind: "link" });
      else if (status === 307 || status === 308) redirects.push(href);
    }
    for (const asset of assets) {
      const status = await statusOf(`${base}${asset}`);
      if (status !== 200) failures.push({ page, target: asset, status, kind: "asset" });
    }

    console.log(
      `  ${String(res.status).padEnd(4)} ${page.padEnd(14)} ${links.size} links, ${assets.size} assets`,
    );
  }

  const guarded = [...new Set(redirects)];
  if (guarded.length > 0) {
    console.log(`\n  ${guarded.length} link(s) redirect to sign-in, which is correct:`);
    console.log(`    ${guarded.join(", ")}`);
  }

  if (failures.length === 0) {
    console.log("\nNothing requested during ordinary loading 404s.");
    return;
  }

  console.log(`\n${failures.length} request(s) did not resolve:\n`);
  for (const f of failures) {
    console.log(`  ${f.status}  ${f.kind.padEnd(5)} ${f.target}\n         linked from ${f.page}`);
  }
  process.exitCode = 1;
}

await main();
