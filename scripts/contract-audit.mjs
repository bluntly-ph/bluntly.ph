#!/usr/bin/env node
/**
 * Which of the API's operations does the product actually call?
 *
 * The feature matrix answers "is this built". This answers the narrower
 * question underneath it: for every operation the backend publishes, is there
 * a line of frontend that calls it — and for every call the frontend makes, is
 * there an operation that answers it. Both halves matter. An operation nothing
 * calls is either dead weight or a capability with no way in; a call to a path
 * the spec does not have is a 404 waiting for a user to find it.
 *
 * It reads `docs/openapi.json`, which is generated from the FastAPI app, and
 * the frontend source. No network, no database, no session: it runs on a clean
 * checkout and reports the same thing every time.
 *
 *   node scripts/contract-audit.mjs
 *   node scripts/contract-audit.mjs --json
 *   node scripts/contract-audit.mjs --strict     # fail on an unanswerable call
 *
 * HOW IT MATCHES, and why it is done this way round. Calls are extracted from
 * source and then routed against the spec, the way the server routes them: a
 * literal path wins over a parameterised one, so `/reviews/feed` is not counted
 * as a call to `/reviews/{review_id}`. Matching spec paths against source text
 * instead — the obvious first attempt — reports every parameterised path as
 * called the moment any sibling literal appears anywhere, which is how this
 * file's first version managed to claim 125 of 125.
 *
 * WHAT A "CALLED" RESULT MEANS, precisely: some source file contains a request
 * for this path. It does not mean the call is correct, reachable, or that the
 * screen around it works — only that the wire between the two sides exists.
 * The method is not checked against the call site either: the fetch helpers
 * pass it in too many shapes to read statically, so an operation counts as
 * called when its path is called. Everything stronger is the e2e suite's job.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const SPEC = join(ROOT, "docs", "openapi.json");
const SELF = "scripts/contract-audit.mjs";

/** Where frontend code that may call the API lives. */
const SOURCE_DIRS = ["app", "components", "lib", "e2e", "scripts"];
const SOURCE_EXT = new Set([".ts", ".tsx", ".mjs", ".js"]);

/**
 * What an interpolated segment becomes.
 *
 * Braces, because no URL path in this codebase contains them and the spec's own
 * `{review_id}` keeps the report readable when a call is printed back out.
 */
const HOLE = "{}";

/**
 * Operations no screen is expected to call, with the reason.
 *
 * An entry here is a claim that has to be true, not a way to quieten the
 * report: each one is reached by something that is not a page.
 */
const NOT_FOR_THE_BROWSER = new Map([
  ["/health", "liveness probe — the platform calls it"],
  ["/r/{review_id}", "affiliate redirect — the browser follows it as a link, never fetches it"],
]);

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    if (entry === "node_modules" || entry === ".next" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    const info = statSync(full);
    if (info.isDirectory()) walk(full, out);
    else if (SOURCE_EXT.has(entry.slice(entry.lastIndexOf(".")))) out.push(full);
  }
  return out;
}

/**
 * Every API path a source file asks for.
 *
 * Both spellings are collected: `/api/v1/...` as a Server Component calls it,
 * and `/api/bff/api/v1/...` as a client component calls it through the
 * forwarder. A `${...}` becomes a single opaque segment, and a query string is
 * dropped — neither changes which operation answers.
 */
function callsIn(text) {
  const found = new Set();
  for (const match of text.matchAll(/["'`](\/api\/(?:bff\/api\/v1|v1)[^"'`]*)["'`]/g)) {
    const raw = match[1]
      .replace(/^\/api\/bff/, "")
      .replace(/\$\{[^}]*\}/g, HOLE)
      .split("?")[0]
      .split("#")[0]
      .replace(/\/+$/, "");
    // A wildcard in a route pattern (`/api/v1/*`) is a declaration, not a call.
    if (raw.includes("*")) continue;
    // `/api/v1` on its own is a prefix in prose or a rewrite rule, not a call.
    if (raw === "/api/v1") continue;
    found.add(raw);
  }
  return found;
}

/**
 * A path the source assembles rather than states.
 *
 * `` `/contracts/${id}${suffix}` `` is three real endpoints written once. No
 * static read can say which, so it is reported as unresolved rather than as a
 * 404 — calling it a broken call would be wrong, and calling it a match to
 * whichever path happens to sort first would be worse.
 */
function isAssembled(call) {
  return call.split("/").some((segment) => segment.includes(HOLE) && segment !== HOLE);
}

/** Route one call against the spec, literal segments before parameters. */
function route(call, specPaths) {
  const parts = call.split("/");
  let best = null;
  for (const spec of specPaths) {
    const specParts = spec.split("/");
    if (specParts.length !== parts.length) continue;
    let literals = 0;
    let ok = true;
    for (let i = 0; i < parts.length; i += 1) {
      const wanted = specParts[i];
      const got = parts[i];
      if (wanted.startsWith("{") && wanted.endsWith("}")) continue;
      if (wanted === got) {
        literals += 1;
        continue;
      }
      // An interpolated segment can stand in for a literal one, but only if
      // nothing more specific matches — hence the score rather than a return.
      if (got === HOLE) continue;
      ok = false;
      break;
    }
    if (!ok) continue;
    if (best === null || literals > best.literals) best = { spec, literals };
  }
  return best?.spec ?? null;
}

function main() {
  const args = process.argv.slice(2);
  const asJson = args.includes("--json");
  const strict = args.includes("--strict");

  const spec = JSON.parse(readFileSync(SPEC, "utf8"));
  const specPaths = Object.keys(spec.paths);

  const sources = SOURCE_DIRS.flatMap((dir) => walk(join(ROOT, dir)))
    .map((file) => ({
      path: relative(ROOT, file).replaceAll("\\", "/"),
      text: readFileSync(file, "utf8"),
    }))
    // This file lists paths in prose and in the excuse table; counting itself
    // as a caller would make every operation look wired up.
    .filter((source) => source.path !== SELF);

  const callers = new Map(specPaths.map((p) => [p, new Set()]));
  const orphanCalls = [];
  const assembledCalls = [];
  for (const source of sources) {
    for (const call of callsIn(source.text)) {
      if (isAssembled(call)) {
        assembledCalls.push({ file: source.path, call });
        continue;
      }
      const matched = route(call, specPaths);
      if (matched) callers.get(matched).add(source.path);
      else orphanCalls.push({ file: source.path, call });
    }
  }

  const operations = [];
  for (const [specPath, methods] of Object.entries(spec.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (!["get", "post", "put", "patch", "delete"].includes(method)) continue;
      operations.push({
        method: method.toUpperCase(),
        path: specPath,
        summary: operation.summary ?? "",
        callers: [...callers.get(specPath)].sort(),
        excused: NOT_FOR_THE_BROWSER.get(specPath) ?? null,
      });
    }
  }

  const called = operations.filter((op) => op.callers.length > 0);
  const uncalled = operations.filter((op) => op.callers.length === 0 && !op.excused);
  const excused = operations.filter((op) => op.callers.length === 0 && op.excused);

  if (asJson) {
    console.log(
      JSON.stringify({ called, uncalled, excused, orphanCalls, assembledCalls }, null, 2),
    );
  } else {
    console.log(
      `API↔frontend contract audit — ${operations.length} operations in docs/openapi.json\n`,
    );
    console.log(`  CALLED BY THE FRONTEND      ${called.length}`);
    console.log(`  NO FRONTEND CALLER          ${uncalled.length}`);
    console.log(`  NOT FOR THE BROWSER         ${excused.length}`);
    console.log(`  CALLS WITH NO OPERATION     ${orphanCalls.length}`);
    console.log(`  CALLS ASSEMBLED AT RUNTIME  ${assembledCalls.length}\n`);

    if (uncalled.length > 0) {
      console.log("Operations no frontend file calls:\n");
      for (const op of uncalled) {
        console.log(`  ${op.method.padEnd(6)} ${op.path}`);
        if (op.summary) console.log(`         ${op.summary}`);
      }
      console.log("");
    }
    if (orphanCalls.length > 0) {
      console.log("Frontend calls the spec cannot answer — each one is a 404:\n");
      for (const orphan of orphanCalls) {
        console.log(`  ${orphan.call}\n         ${orphan.file}`);
      }
      console.log("");
    }
    if (assembledCalls.length > 0) {
      console.log("Calls assembled at runtime — read these by hand, not here:\n");
      for (const assembled of assembledCalls) {
        console.log(`  ${assembled.call}\n         ${assembled.file}`);
      }
      console.log("");
    }
  }

  if (strict && orphanCalls.length > 0) process.exit(1);
}

main();
