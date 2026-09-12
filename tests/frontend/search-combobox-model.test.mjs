import assert from "node:assert/strict";
import test from "node:test";

import { comboKeyAction } from "../../components/search/search-combobox-model.ts";

const state = (overrides = {}) => ({
  open: true,
  dismissed: false,
  eligible: true,
  itemCount: 3,
  active: -1,
  ...overrides,
});

/**
 * The regression this file exists for.
 *
 * `<input type="search">` clears itself on Escape. The handler dismissed the
 * list but did not suppress that default, so the query was wiped — contradicting
 * the documented behaviour and leaving nothing for ArrowDown to reopen.
 * Production QA found it; types and lint could not, because a missing
 * `preventDefault()` is not a type error.
 */
test("Escape closes an open list and suppresses the native search clear", () => {
  const action = comboKeyAction("Escape", state({ open: true }));

  assert.equal(action.type, "dismiss");
  assert.equal(
    action.preventDefault,
    true,
    "without preventDefault the browser empties a type=search input, losing the query",
  );
});

test("Escape on an already-closed list lets the native clear through", () => {
  const action = comboKeyAction("Escape", state({ open: false, dismissed: true }));

  assert.equal(action.type, "dismiss");
  assert.equal(
    action.preventDefault,
    false,
    "a second Escape should still clear the field — that affordance is not removed",
  );
});

test("ArrowDown reopens a dismissed list and highlights its first option", () => {
  const action = comboKeyAction("ArrowDown", state({ open: false, dismissed: true }));

  assert.equal(action.type, "reopen");
  assert.equal(action.preventDefault, true);
  // The ARIA combobox pattern: opening with ArrowDown moves visual focus to the
  // first option. Reopening with no highlight left aria-activedescendant empty
  // on a visible list and made ArrowDown a two-press affair.
  assert.equal(action.to, 0);
});

test("ArrowDown re-enables searching when the query is eligible but nothing is held", () => {
  const action = comboKeyAction(
    "ArrowDown",
    state({ open: false, dismissed: true, itemCount: 0, eligible: true }),
  );

  assert.equal(action.type, "reopen");
  // Not prevented: there is no list to move within, so the caret may move.
  assert.equal(action.preventDefault, false);
  // Nothing has been fetched for this query yet, so there is nothing to highlight.
  assert.equal(action.to, null);
});

test("ArrowDown from no highlight selects the first suggestion", () => {
  assert.deepEqual(comboKeyAction("ArrowDown", state({ active: -1 })), {
    type: "move",
    to: 0,
    preventDefault: true,
  });
});

test("ArrowDown wraps past the last suggestion", () => {
  assert.deepEqual(comboKeyAction("ArrowDown", state({ active: 2, itemCount: 3 })), {
    type: "move",
    to: 0,
    preventDefault: true,
  });
});

test("ArrowUp wraps from the first suggestion to the last", () => {
  assert.deepEqual(comboKeyAction("ArrowUp", state({ active: 0, itemCount: 3 })), {
    type: "move",
    to: 2,
    preventDefault: true,
  });
});

test("ArrowUp from no highlight lands on the last suggestion", () => {
  assert.deepEqual(comboKeyAction("ArrowUp", state({ active: -1, itemCount: 3 })), {
    type: "move",
    to: 2,
    preventDefault: true,
  });
});

test("Enter accepts the highlighted suggestion", () => {
  assert.deepEqual(comboKeyAction("Enter", state({ active: 1 })), {
    type: "choose",
    index: 1,
    preventDefault: true,
  });
});

test("Enter with nothing highlighted submits the form instead", () => {
  const action = comboKeyAction("Enter", state({ active: -1 }));

  assert.equal(action.type, "none");
  assert.equal(
    action.preventDefault,
    false,
    "the field stays a real GET form: Enter must search exactly what was typed",
  );
});

test("ordinary typing is never intercepted", () => {
  for (const key of ["a", "Backspace", "Tab", "Home", " "]) {
    const action = comboKeyAction(key, state());
    assert.equal(action.type, "none", `${key} should pass through`);
    assert.equal(action.preventDefault, false, `${key} should not be prevented`);
  }
});

test("keys other than ArrowDown do nothing while the list is closed", () => {
  for (const key of ["ArrowUp", "Enter", "a"]) {
    const action = comboKeyAction(key, state({ open: false, dismissed: true, active: 1 }));
    assert.equal(action.type, "none", `${key} should do nothing with the list closed`);
  }
});
