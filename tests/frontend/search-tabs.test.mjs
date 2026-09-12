import assert from "node:assert/strict";
import test from "node:test";

import { searchTabHref } from "../../components/search/search-tabs-model.ts";

/**
 * The tabs are links to real URLs, so what they carry across is the contract:
 * the reader's query follows them, and a filter that means nothing on the other
 * side does not.
 */

test("the query follows the reader to the other tab", () => {
  assert.equal(searchTabHref("questions", { q: "jisulife" }), "/search?q=jisulife&tab=questions");
  assert.equal(searchTabHref("reviews", { q: "jisulife" }), "/search?q=jisulife");
});

test("reviews is the default tab and carries no tab parameter", () => {
  assert.equal(searchTabHref("reviews", {}), "/search");
  assert.equal(searchTabHref("questions", {}), "/search?tab=questions");
});

test("a category narrows reviews and is not carried to questions", () => {
  assert.equal(
    searchTabHref("reviews", { q: "fan", category: "audio" }),
    "/search?q=fan&category=audio",
  );
  // Categories do not apply to questions; carrying one would put a filter in the
  // URL that silently does nothing.
  assert.equal(searchTabHref("questions", { q: "fan", category: "audio" }), "/search?q=fan&tab=questions");
});

test("the categories back-link context survives both tabs", () => {
  assert.equal(
    searchTabHref("questions", { q: "fan", from: "categories" }),
    "/search?q=fan&tab=questions&from=categories",
  );
});

test("a blank query is not carried as an empty parameter", () => {
  assert.equal(searchTabHref("questions", { q: "   " }), "/search?tab=questions");
  assert.equal(searchTabHref("reviews", { q: "" }), "/search");
});

test("a query with spaces and symbols is encoded", () => {
  assert.equal(
    searchTabHref("questions", { q: "jisulife fan & noise" }),
    "/search?q=jisulife+fan+%26+noise&tab=questions",
  );
});
