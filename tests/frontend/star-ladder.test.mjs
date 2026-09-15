import assert from "node:assert/strict";
import test from "node:test";

import { STAR_EMPTY, starColor } from "../../components/ui/star-ladder.ts";

/**
 * Figma "Icon/Star" (6805:431): filled stars take the rating ladder's colour —
 * the file's own cards draw two stars coral, three yellow, four and five green.
 * Owner review (2026-09-16) found the rating inputs all green at every value.
 */

test("one and two stars are coral", () => {
  assert.equal(starColor(1), "var(--brand-coral)");
  assert.equal(starColor(2), "var(--brand-coral)");
});

test("three stars are yellow", () => {
  assert.equal(starColor(3), "var(--semantic-star)");
});

test("four and five stars are the rating green", () => {
  assert.equal(starColor(4), "var(--semantic-success-500)");
  assert.equal(starColor(5), "var(--semantic-success-500)");
});

test("no rating, or a nonsense one, draws the empty grey", () => {
  assert.equal(starColor(null), STAR_EMPTY);
  assert.equal(starColor(0), STAR_EMPTY);
  assert.equal(starColor(Number.NaN), STAR_EMPTY);
});

test("an average is graded by its rounded value", () => {
  assert.equal(starColor(2.4), "var(--brand-coral)");
  assert.equal(starColor(2.6), "var(--semantic-star)");
  assert.equal(starColor(3.5), "var(--semantic-success-500)");
});
