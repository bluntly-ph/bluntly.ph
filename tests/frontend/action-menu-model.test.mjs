import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTION_MENU_ITEMS,
  DISABLED_REASON,
  isActionable,
} from "../../components/site/action-menu-model.ts";

/**
 * "Rate a Seller" was drawn and shipped disabled while no seller entity
 * existed. The completion contract reinstated the seller flow (sellers,
 * claims, seller reviews), so it now opens the seller composer. What stays
 * locked is the rule that made the disabled state honest: nothing is enabled
 * without a real route behind it.
 */

const byKey = (k) => ACTION_MENU_ITEMS.find((i) => i.key === k);

test("the menu offers exactly the three drawn actions, in order", () => {
  assert.deepEqual(
    ACTION_MENU_ITEMS.map((i) => i.label),
    ["Ask a Question", "Rate a Seller", "Write a Review"],
  );
});

test("Rate a Seller opens the seller composer", () => {
  const seller = byKey("seller");
  assert.equal(seller.enabled, true);
  assert.equal(seller.href, "/sellers/rate");
  assert.equal(isActionable(seller), true);
});

test("no action is left disabled, so none needs a reason", () => {
  for (const item of ACTION_MENU_ITEMS) {
    assert.equal(isActionable(item), true, `${item.key} should be actionable`);
  }
  assert.deepEqual(DISABLED_REASON, {});
});

test("the actions point at routes that exist", () => {
  assert.equal(byKey("ask").href, "/questions/new");
  assert.equal(byKey("review").href, "/reviews/new");
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
