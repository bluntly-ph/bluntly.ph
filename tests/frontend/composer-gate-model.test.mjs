import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_TITLE,
  MIN_PROSE,
  blockerFor,
  buttonLabel,
  counterIsSatisfied,
  counterLabel,
  remaining,
} from "../../components/reviews/composer-gate-model.ts";

/**
 * These numbers are the reviewer pack's, not preferences, and the pack is the
 * only place they are written down. A test is what stops "30 characters
 * remaining" quietly becoming 40 again, or the last step's button drifting
 * back to "Submit for review".
 */

const EMPTY = {
  discussion: "",
  verdict: null,
  rating: 0,
  pros: "",
  cons: "",
  anti: "",
  photoUrl: null,
  title: "",
};

const filled = (over) => ({ ...EMPTY, ...over });
const SENTENCE = "Anyone who needs it to fit in a very small pocket";

test("the prose floor and the title ceiling are the frame's", () => {
  assert.equal(MIN_PROSE, 30, "step 1.1 and step 5 both count down from 30");
  assert.equal(MAX_TITLE, 30, 'step 7 reads "0/30 characters"');
});

test("remaining counts down to zero and stops", () => {
  assert.equal(remaining(""), 30);
  assert.equal(remaining("a".repeat(10)), 20);
  assert.equal(remaining("a".repeat(30)), 0);
  assert.equal(remaining("a".repeat(500)), 0, "a floor, not a limit");
});

test("whitespace does not count toward the floor", () => {
  assert.equal(remaining("   " + "a".repeat(30) + "   "), 0);
  assert.equal(remaining(" ".repeat(50)), 30, "spaces alone are not a review");
});

test("the counter is the countdown, then the step's own line", () => {
  assert.equal(counterLabel("", "Solid review!"), "30 characters remaining");
  assert.equal(counterLabel("a".repeat(29), "Solid review!"), "1 characters remaining");
  assert.equal(counterLabel("a".repeat(30), "Solid review!"), "Solid review!");
  assert.equal(
    counterLabel("a".repeat(30), "I'm sure someone will appreciate this"),
    "I'm sure someone will appreciate this",
    "step 5 has its own sentence",
  );
});

test("satisfied is exactly when the countdown reaches zero", () => {
  assert.equal(counterIsSatisfied("a".repeat(29)), false);
  assert.equal(counterIsSatisfied("a".repeat(30)), true);
});

test("every step blocks while empty", () => {
  for (const step of [0, 1, 2, 3, 4, 5, 6]) {
    assert.ok(blockerFor(step, EMPTY), `step ${step} let an empty draft through`);
  }
});

test("step 1 gates on the same 30 as its counter", () => {
  assert.ok(blockerFor(0, filled({ discussion: "a".repeat(29) })));
  assert.equal(blockerFor(0, filled({ discussion: "a".repeat(30) })), null);
});

test("step 5 gates on the same 30 as its counter", () => {
  assert.ok(blockerFor(4, filled({ anti: "too short" })));
  assert.equal(blockerFor(4, filled({ anti: SENTENCE })), null);
});

test("pros and cons are both required, not either", () => {
  assert.ok(blockerFor(3, filled({ pros: "Worth it!" })), "a pro alone is not enough");
  assert.ok(blockerFor(3, filled({ cons: "Too Heavy" })), "a con alone is not enough");
  assert.equal(blockerFor(3, filled({ pros: "Worth it!", cons: "Too Heavy" })), null);
});

test("blank lines do not count as a pro or a con", () => {
  assert.ok(blockerFor(3, filled({ pros: "\n  \n", cons: "\n" })));
});

test("step 6 gates on the photo — Skip is a route past it, not an unlock", () => {
  assert.ok(blockerFor(5, EMPTY), "the frame greys Continue with no photo");
  assert.equal(blockerFor(5, filled({ photoUrl: "https://cdn/x.jpg" })), null);
});

test("a zero rating is not a rating", () => {
  assert.ok(blockerFor(2, filled({ rating: 0 })));
  assert.equal(blockerFor(2, filled({ rating: 1 })), null);
});

test("only the last step submits", () => {
  assert.equal(buttonLabel(0, 7, false), "Continue");
  assert.equal(buttonLabel(5, 7, false), "Continue");
  assert.equal(buttonLabel(6, 7, false), "Submit");
  assert.equal(buttonLabel(6, 7, true), "Submitting…");
});

test("an unknown step blocks nothing rather than throwing", () => {
  assert.equal(blockerFor(99, EMPTY), null);
});
