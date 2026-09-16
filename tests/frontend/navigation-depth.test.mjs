import assert from "node:assert/strict";
import test from "node:test";

import {
  canGoBackInApp,
  canGoBackOnServer,
  markPopstate,
  recordPath,
  resetNavigationDepth,
  subscribeNavigationDepth,
} from "../../lib/navigation-depth.ts";

/**
 * Whether the site's Back control may use history (BUG-033).
 *
 * The one outcome this model must never produce is "yes" when the page behind
 * is not ours: that turns Back into a button that takes the reader off the
 * site. The first implementation did exactly that for a review opened in a new
 * tab, and a browser test caught it. Every case below is about which way an
 * uncertainty is allowed to err.
 */

test.beforeEach(() => resetNavigationDepth());

test("a page opened cold has nothing in-app behind it", () => {
  recordPath("/reviews/abc");
  assert.equal(canGoBackInApp(), false);
});

test("an in-app navigation puts a page behind the current one", () => {
  recordPath("/search");
  recordPath("/reviews/abc");
  assert.equal(canGoBackInApp(), true);
});

test("going back to the entry page leaves nothing behind it", () => {
  recordPath("/search");
  recordPath("/reviews/abc");
  markPopstate();
  recordPath("/search");
  assert.equal(canGoBackInApp(), false, "back at the entry point, Back must not use history");
});

test("two steps in and one back still has one page behind", () => {
  recordPath("/");
  recordPath("/search");
  recordPath("/reviews/abc");
  markPopstate();
  recordPath("/search");
  assert.equal(canGoBackInApp(), true);
});

test("the depth never goes negative, however many backs arrive", () => {
  recordPath("/reviews/abc");
  for (const path of ["/a", "/b", "/c"]) {
    markPopstate();
    recordPath(path);
  }
  assert.equal(canGoBackInApp(), false);
});

test("re-recording the same path is not a navigation", () => {
  // Effects re-run; a re-render must not invent history.
  recordPath("/reviews/abc");
  recordPath("/reviews/abc");
  recordPath("/reviews/abc");
  assert.equal(canGoBackInApp(), false);
});

test("the server never claims history", () => {
  assert.equal(canGoBackOnServer(), false);
});

test("subscribers hear about a navigation, and can unsubscribe", () => {
  let calls = 0;
  const unsubscribe = subscribeNavigationDepth(() => {
    calls += 1;
  });
  recordPath("/search");
  recordPath("/reviews/abc");
  assert.equal(calls, 1, "the entry path is not a change; the second path is");

  unsubscribe();
  recordPath("/reviews/def");
  assert.equal(calls, 1);
});
