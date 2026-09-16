import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

/**
 * The `?next=` return path, and the query it has to carry.
 *
 * Two files have to agree: `proxy.ts` builds the value, `safeNext` in
 * `app/actions/auth.ts` resolves it after sign-in. They disagreed until
 * 2026-09-16 — the proxy sent only the pathname while `safeNext` was perfectly
 * capable of keeping a query — so a reader who bookmarked `/profile?tab=stats`
 * signed in and landed on a different tab. Nothing failed; they were simply put
 * somewhere they had not asked for.
 *
 * `safeNext` is exercised as a function below (it is small, pure and the whole
 * security boundary); the proxy's half is asserted at the source, because the
 * only other way to reach it is an end-to-end run, which `e2e/route-guards.spec.ts`
 * also covers.
 */

const PROXY = readFileSync(new URL("../../proxy.ts", import.meta.url), "utf8").replace(
  /\r/g,
  "",
);

/** The real implementation, copied from app/actions/auth.ts and pinned below. */
const INTERNAL_ONLY = "https://next.invalid";

function safeNext(raw) {
  const value = typeof raw === "string" ? raw : "";
  if (!value.startsWith("/")) return "/";
  try {
    const resolved = new URL(value, INTERNAL_ONLY);
    if (resolved.origin !== INTERNAL_ONLY) return "/";
    const destination = `${resolved.pathname}${resolved.search}${resolved.hash}`;
    if (!destination.startsWith("/") || destination.startsWith("//")) return "/";
    return destination;
  } catch {
    return "/";
  }
}

test("the copy of safeNext here matches the one that actually runs", () => {
  // A test that quietly drifts from the implementation it claims to cover is
  // worse than no test, so the source is compared rather than trusted.
  const source = readFileSync(
    new URL("../../app/actions/auth.ts", import.meta.url),
    "utf8",
  ).replace(/\r/g, "");
  const real = source.slice(
    source.indexOf("function safeNext"),
    source.indexOf("\n}\n", source.indexOf("function safeNext")) + 2,
  );
  const normalise = (text) =>
    text
      .replace(/\/\/.*$/gm, "")
      .replace(/raw: FormDataEntryValue \| null/, "raw")
      .replace(/function safeNext\(raw\): string/, "function safeNext(raw)")
      .replace(/\s+/g, " ")
      .trim();

  assert.equal(normalise(real), normalise(safeNext.toString()));
});

test("the proxy sends the query back, not just the path", () => {
  assert.match(
    PROXY,
    /url\.searchParams\.set\("next", `\$\{pathname\}\$\{request\.nextUrl\.search\}`\)/,
    "proxy.ts must put pathname AND search into ?next=",
  );
});

test("a tabbed destination survives the round trip", () => {
  for (const destination of [
    "/profile?tab=stats",
    "/profile?tab=comments",
    "/moderate/review-queue?tab=report&band=high",
    "/dashboard",
  ]) {
    assert.equal(safeNext(destination), destination);
  }
});

test("a fragment survives too", () => {
  assert.equal(safeNext("/reviews/abc#comments"), "/reviews/abc#comments");
});

test("nothing that leaves the origin survives, query or not", () => {
  for (const hostile of [
    "https://evil.example/",
    "//evil.example/",
    "/\\evil.example",
    "/..//evil.example",
    "/\tevil.example",
    "javascript:alert(1)",
    "",
    null,
  ]) {
    const result = safeNext(hostile);

    // The test is whether the result can leave this origin, not whether the
    // attacker's hostname appears in it. `/\tevil.example` legitimately
    // resolves to the PATH `/evil.example` — the tab is dropped, and a path on
    // our own site named after someone else's domain is harmless.
    assert.ok(
      result.startsWith("/") && !result.startsWith("//"),
      `${JSON.stringify(hostile)} resolved to ${result}`,
    );
    assert.equal(
      new URL(result, "https://www.bluntly.ph").origin,
      "https://www.bluntly.ph",
      `${JSON.stringify(hostile)} escaped the origin`,
    );
  }
});
