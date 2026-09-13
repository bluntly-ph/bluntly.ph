import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTION_MENU_ITEMS,
  DISABLED_REASON,
  isActionable,
} from "../../components/site/action-menu-model.ts";

/**
 * The contract worth locking here is the surprising one: a visible action that
 * deliberately does nothing. Without a test, "Rate a Seller has no href" reads
 * like an oversight and is one confident cleanup away from being wired to a
 * route that does not exist.
 */

const byKey = (k) => ACTION_MENU_ITEMS.find((i) => i.key === k);

test("the menu offers exactly the three drawn actions, in order", () => {
  assert.deepEqual(
    ACTION_MENU_ITEMS.map((i) => i.label),
    ["Ask a Question", "Rate a Seller", "Write a Review"],
  );
});

test("Rate a Seller is present but not actionable", () => {
  const seller = byKey("seller");

  assert.ok(seller, "it must stay visible — the design says the capability exists");
  assert.equal(seller.enabled, false);
  assert.equal(seller.href, null, "there is no seller entity to link to");
  assert.equal(isActionable(seller), false);
});

test("a disabled action explains itself to assistive technology", () => {
  assert.match(DISABLED_REASON.seller, /not available/i);
});

test("the two real actions point at routes that exist", () => {
  assert.equal(byKey("ask").href, "/questions/new");
  assert.equal(byKey("review").href, "/reviews/new");
  assert.equal(isActionable(byKey("ask")), true);
  assert.equal(isActionable(byKey("review")), true);
});

test("no action is enabled without somewhere to go", () => {
  for (const item of ACTION_MENU_ITEMS) {
    if (item.enabled) {
      assert.ok(item.href, `${item.key} is enabled and must have an href`);
    }
  }
});

test("isActionable refuses an enabled item with an empty href", () => {
  assert.equal(isActionable({ key: "x", label: "X", href: "", enabled: true }), false);
  assert.equal(isActionable({ key: "x", label: "X", href: null, enabled: true }), false);
});
