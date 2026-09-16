#!/usr/bin/env node
/**
 * How heavy is a page, in bytes that actually cross the wire?
 *
 * The owner's report is "bigat pa rin ng responsive ng website" — it still
 * feels heavy. That is a real complaint and it needs a number, because the
 * checks we already had cannot see it: "no horizontal overflow" and a
 * Lighthouse score of 100 were both true while the site was shipping close to
 * a megabyte of JavaScript per page.
 *
 *   node scripts/page-weight.mjs                        # production
 *   node scripts/page-weight.mjs http://localhost:3000
 *
 * It reports each page's HTML, the JavaScript and CSS it references, and the
 * total, in DECOMPRESSED bytes — what the browser parses, which is what costs
 * time on a mid-range phone.
 *
 * IT DOES NOT REPORT TRANSFER SIZE, and the reason is worth knowing because it
 * produced a wrong answer first: Node's `fetch` decompresses transparently and
 * `arrayBuffer()` hands back the decompressed bytes, so asking for `br` and
 * asking for `identity` return the same length. An earlier version of this
 * script printed both and concluded the site served no compression at all.
 * It does — `curl -s -o /dev/null -w '%{size_download}' --compressed <url>`
 * is the way to measure that, and production answers `Content-Encoding: br`.
 *
 * WHAT IT IS NOT: a Lighthouse run. It measures bytes, not paint. LCP, CLS and
 * INP need a real browser and belong in the audit harness. Bytes are the part
 * that can be tracked in a shell and compared between deploys.
 */

const base = (process.argv[2] ?? "https://www.bluntly.ph").replace(/\/$/, "");
const PAGES = process.argv.length > 3
  ? process.argv.slice(3)
  : ["/", "/search", "/feed", "/categories", "/questions", "/requests"];

/** Decompressed size for one URL, in bytes. See the note above on transfer size. */
async function weigh(url) {
  const res = await fetch(url);
  const body = await res.arrayBuffer();
  return { raw: body.byteLength, status: res.status, text: body };
}

const kb = (n) => (n / 1024).toFixed(1).padStart(8);

async function main() {
  console.log(`page weight — ${base}\n`);
  console.log(
    `${"page".padEnd(13)} ${"html".padStart(8)} ${"js".padStart(8)} ${"css".padStart(8)} ` +
      `${"total".padStart(9)}  files   (KB, decompressed)`,
  );

  for (const page of PAGES) {
    const doc = await weigh(`${base}${page}`);
    const html = new TextDecoder().decode(doc.text);
    const assets = new Set([
      ...[...html.matchAll(/"(\/_next\/[^"]+\.(?:js|css))"/g)].map((m) => m[1]),
      ...[...html.matchAll(/href="(\/_next\/[^"]+\.css)"/g)].map((m) => m[1]),
    ]);

    let js = 0;
    let css = 0;
    for (const asset of assets) {
      const a = await weigh(`${base}${asset}`);
      if (asset.endsWith(".js")) js += a.raw;
      else css += a.raw;
    }
    const total = doc.raw + js + css;
    console.log(
      `${page.padEnd(13)} ${kb(doc.raw)} ${kb(js)} ${kb(css)} ${kb(total)}  ${assets.size}`,
    );
  }

  console.log(
    "\nDecompressed bytes — what the browser parses. The network carries far\n" +
      "less (production serves brotli); compression helps the download and not\n" +
      "the CPU, and the CPU is what a mid-range phone runs out of first.",
  );
}

await main();
