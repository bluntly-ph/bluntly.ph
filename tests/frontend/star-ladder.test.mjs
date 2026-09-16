import assert from "node:assert/strict";
import test from "node:test";

import {
  STAR_EMPTY,
  STAR_STEPS,
  formatRating,
  hasRating,
  starColor,
  starFill,
} from "../../components/ui/star-ladder.ts";

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

/**
 * Half steps and zero (owner requirement, 2026-09-16). Zero is an answer, so it
 * must not read as "unanswered" anywhere in the stack.
 */

test("a half fills the stars below it and halves its own", () => {
  assert.deepEqual([1, 2, 3, 4, 5].map((n) => starFill(n, 3.5)), [
    "full",
    "full",
    "full",
    "half",
    "empty",
  ]);
  assert.deepEqual([1, 2, 3, 4, 5].map((n) => starFill(n, 0.5)), [
    "half",
    "empty",
    "empty",
    "empty",
    "empty",
  ]);
  assert.deepEqual([1, 2, 3, 4, 5].map((n) => starFill(n, 4.5)), [
    "full",
    "full",
    "full",
    "full",
    "half",
  ]);
});

test("zero is a rating, and it draws no stars", () => {
  assert.deepEqual([1, 2, 3, 4, 5].map((n) => starFill(n, 0)), Array(5).fill("empty"));
  assert.equal(hasRating(0), true, "zero has been answered");
  assert.equal(hasRating(null), false, "null has not");
  assert.equal(formatRating(0), "0");
});

test("five fills every star", () => {
  assert.deepEqual([1, 2, 3, 4, 5].map((n) => starFill(n, 5)), Array(5).fill("full"));
});

test("a rating reads back as it was given", () => {
  assert.equal(formatRating(4), "4");
  assert.equal(formatRating(4.5), "4.5");
  assert.equal(formatRating(3.5), "3.5");
  assert.equal(formatRating(null), "—");
});

test("the control offers every step the API accepts", () => {
  assert.deepEqual([...STAR_STEPS], [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]);
});
