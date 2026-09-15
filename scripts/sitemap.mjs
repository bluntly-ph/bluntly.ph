// The site map from lib/site-map.ts, for people and for page checks.
//
//   npm run sitemap:docs                  rewrite docs/SITEMAP.md
//   npm run sitemap -- --paths            every page path, one per line
//   npm run sitemap -- --paths public     only pages with that access level
//
// Dynamic paths print with their brackets (/reviews/[id]); a checker fills in
// a real id.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { SITE_ROUTES, siteMapMarkdown } from "../lib/site-map.ts";

const args = process.argv.slice(2);

if (args[0] === "--paths") {
  const access = args[1];
  for (const route of SITE_ROUTES) {
    if (!access || route.access === access) console.log(route.path);
  }
} else if (args[0] === "--write-docs") {
  const target = fileURLToPath(new URL("../docs/SITEMAP.md", import.meta.url));
  writeFileSync(target, siteMapMarkdown());
  console.log(`wrote docs/SITEMAP.md (${SITE_ROUTES.length} pages)`);
} else {
  process.stdout.write(siteMapMarkdown());
}
