import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { isAuthOnlyPath, isProtectedPath } from "../../lib/route-access.ts";
import { SITE_ROUTES, SYSTEM_ROUTES, siteMapMarkdown, sitemapPaths } from "../../lib/site-map.ts";

/**
 * The site map is only worth having if it cannot drift: a page added without
 * an entry, an entry left behind by a deleted page, or an access level that the
 * proxy does not actually enforce all fail here.
 */

const ROOT = fileURLToPath(new URL("../../", import.meta.url));

function filesNamed(dir, names) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) found.push(...filesNamed(full, names));
    else if (names.includes(entry)) found.push(relative(ROOT, full).split(sep).join("/"));
  }
  return found;
}

/** app/(auth)/login/page.tsx -> /login; route groups are not part of the URL. */
function routeOf(file) {
  const segments = file
    .replace(/^app\//, "")
    .replace(/\/?(page|route)\.tsx?$/, "")
    .split("/")
    .filter((s) => s && !/^\(.*\)$/.test(s));
  return `/${segments.join("/")}`;
}

/** A concrete URL for a pattern, so the proxy's rules can be run against it. */
const sample = (pattern) => pattern.replace(/\[\.\.\.[^\]]+\]/g, "a/b").replace(/\[[^\]]+\]/g, "sample-id");

test("every page in app/ has exactly one entry, and every entry has a page", () => {
  const pages = filesNamed(join(ROOT, "app"), ["page.tsx"]).sort();
  const listed = SITE_ROUTES.map((r) => r.file).sort();
  assert.deepEqual(listed, pages);
  assert.equal(new Set(listed).size, listed.length, "a page is listed twice");
});

test("each entry's path is the URL its file serves", () => {
  for (const route of SITE_ROUTES) {
    assert.equal(route.path, routeOf(route.file), route.file);
  }
});

test("every route handler in app/ is listed as a system route", () => {
  const handlers = filesNamed(join(ROOT, "app"), ["route.ts", "route.tsx"]).map(routeOf).sort();
  const listed = SYSTEM_ROUTES.filter((r) => r.source === "app").map((r) => r.path).sort();
  assert.deepEqual(listed, handlers);
});

test("signed-in, moderator and store-owner pages are gated by the proxy", () => {
  for (const route of SITE_ROUTES.filter((r) => r.access !== "public" && r.access !== "signed-out")) {
    assert.ok(isProtectedPath(sample(route.path)), `${route.path} is ${route.access} but the proxy lets it through`);
  }
});

test("public pages are not gated, and signed-out pages are the auth-only ones", () => {
  for (const route of SITE_ROUTES) {
    const url = sample(route.path);
    if (route.access === "public") {
      assert.ok(!isProtectedPath(url), `${route.path} is public but the proxy gates it`);
      assert.ok(!isAuthOnlyPath(url), `${route.path} is public but hidden from signed-in readers`);
    }
    if (route.access === "signed-out") assert.ok(isAuthOnlyPath(url), route.path);
  }
});

test("moderator pages all live under /moderate", () => {
  for (const route of SITE_ROUTES.filter((r) => r.access === "moderator")) {
    assert.match(route.path, /^\/moderate(\/|$)/);
  }
});

test("the store dashboard keeps its return path through login", () => {
  assert.equal(isProtectedPath("/sellers/5e11e700/dashboard"), true);
  assert.equal(isProtectedPath("/sellers/5e11e700"), false);
  assert.equal(isProtectedPath("/sellers/rate"), true);
});

test("sitemap.xml lists only public pages with a fixed URL", () => {
  const paths = sitemapPaths();
  assert.ok(paths.includes("/"));
  for (const path of paths) {
    const route = SITE_ROUTES.find((r) => r.path === path);
    assert.ok(route, path);
    assert.equal(route.access, "public", path);
    assert.doesNotMatch(path, /\[/, path);
  }
});

test("every entry says what the page is for and where its design comes from", () => {
  for (const route of SITE_ROUTES) {
    assert.ok(route.title.trim(), route.path);
    assert.ok(route.purpose.trim().length > 10, route.path);
    assert.ok(route.figma === null || route.figma.trim().length > 0, route.path);
  }
});

test("docs/SITEMAP.md is the generated table (npm run sitemap:docs)", () => {
  const file = join(ROOT, "docs", "SITEMAP.md");
  assert.ok(existsSync(file), "docs/SITEMAP.md is missing");
  const onDisk = readFileSync(file, "utf8").replace(/\r\n/g, "\n");
  assert.equal(onDisk, siteMapMarkdown());
});
