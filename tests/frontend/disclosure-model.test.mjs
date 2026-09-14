import assert from "node:assert/strict";
import test from "node:test";

import { DISCLOSURE_OPTIONS, disclosureLabel } from "../../components/reviews/disclosure-model.ts";

/**
 * Disclosure of a material relationship (completion contract X.1).
 *
 * A reviewer says whether they bought the product themselves, got it free or
 * discounted, or are connected to the brand or seller. Readers see the last two
 * on the review. "No" shows nothing — it is the ordinary case — and a review
 * written before the question existed shows nothing either, rather than being
 * labelled with an answer its author never gave.
 */

test("the three answers, in the order they are offered", () => {
  assert.deepEqual(
    DISCLOSURE_OPTIONS.map((o) => o.value),
    ["none", "free_or_discounted", "connected"],
  );
  for (const option of DISCLOSURE_OPTIONS) assert.ok(option.label.length > 0);
});

test("a relationship is shown to readers", () => {
  assert.match(disclosureLabel("free_or_discounted"), /free or discounted/i);
  assert.match(disclosureLabel("connected"), /connected to the brand or seller/i);
});

test("no relationship, and a review never asked, show nothing", () => {
  assert.equal(disclosureLabel("none"), null);
  assert.equal(disclosureLabel(null), null);
  assert.equal(disclosureLabel(undefined), null);
});
