import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_RECENT_SEARCHES,
  parseRecentSearches,
  rememberSearch,
} from "../../components/search/recent-searches-model.ts";

/**
 * The typing state of "Screen/Mobile Search" (6852:641) lists the reader's own
 * recent searches: three rows, newest first. They live only on this device, so
 * what is stored must survive being hand-edited or corrupted.
 */

test("the frame's three rows are the cap", () => {
  assert.equal(MAX_RECENT_SEARCHES, 3);
});

test("a new search goes to the top", () => {
  assert.deepEqual(rememberSearch(["jisulife fan"], "fragranceph legit check"), [
    "fragranceph legit check",
    "jisulife fan",
  ]);
});

test("repeating a search moves it up instead of listing it twice, whatever its case", () => {
  assert.deepEqual(rememberSearch(["a", "Jisulife Fan", "b"], "jisulife fan"), ["jisulife fan", "a", "b"]);
});

test("only the newest three are kept", () => {
  assert.deepEqual(rememberSearch(["c", "b", "a"], "d"), ["d", "c", "b"]);
});

test("blank searches are not remembered, and whitespace is trimmed", () => {
  assert.deepEqual(rememberSearch(["a"], "   "), ["a"]);
  assert.deepEqual(rememberSearch([], "  best fan  "), ["best fan"]);
});

test("stored data that is not a list of strings reads as no history", () => {
  assert.deepEqual(parseRecentSearches(null), []);
  assert.deepEqual(parseRecentSearches("not json"), []);
  assert.deepEqual(parseRecentSearches('{"a":1}'), []);
  assert.deepEqual(parseRecentSearches('["ok", 3, "", "fine"]'), ["ok", "fine"]);
});
