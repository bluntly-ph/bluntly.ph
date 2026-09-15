import assert from "node:assert/strict";
import test from "node:test";

import {
  MIN_QUESTION_CHARS,
  QUESTION_REQUIREMENTS,
  composeQuestionBody,
  splitQuestionBody,
} from "../../components/qa/ask-question-model.ts";

/**
 * "Are there any specifics you'd like to know?" has nowhere of its own to live
 * in the API, so the chosen specifics travel inside the question as a final
 * "Looking for:" line — and the question pages read them back out as the
 * "Requirements:" tags the Question Page frame draws.
 */

test("a question with no specifics is sent as written, trimmed", () => {
  assert.equal(composeQuestionBody("  Is it loud?  ", []), "Is it loud?");
});

test("chosen specifics follow on their own line, once each, in the picker's order", () => {
  assert.equal(
    composeQuestionBody("Is this good for traveling?", ["Rating", "Experience", "Rating"]),
    "Is this good for traveling?\n\nLooking for: Experience, Rating",
  );
});

test("reading a question back separates the specifics from the words", () => {
  assert.deepEqual(
    splitQuestionBody("Is this good for traveling?\n\nLooking for: Experience, Pros & Cons"),
    { text: "Is this good for traveling?", requirements: ["Experience", "Pros & Cons"] },
  );
});

test("a last line that only looks like specifics stays part of the question", () => {
  const body = "Worth it?\n\nLooking for: a cheaper one";
  assert.deepEqual(splitQuestionBody(body), { text: body, requirements: [] });
});

test("every specific survives the round trip", () => {
  for (const r of QUESTION_REQUIREMENTS) {
    const body = composeQuestionBody("How is the battery?", [r]);
    assert.deepEqual(splitQuestionBody(body), { text: "How is the battery?", requirements: [r] });
  }
});

test("the question needs the frame's 15 characters", () => {
  assert.equal(MIN_QUESTION_CHARS, 15);
});
