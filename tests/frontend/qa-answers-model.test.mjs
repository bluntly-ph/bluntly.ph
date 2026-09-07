import assert from "node:assert/strict";
import test from "node:test";

import {
  answerPhotos,
  answerTabLabel,
  qaAuthorStats,
  questionRows,
  questionEmptyMessage,
  selectAnswer,
} from "../../components/admin/qa-answers-model.ts";

/** A `QAAuthor` exactly as `backend/app/schemas/qa.py` serializes one. */
const author = (overrides = {}) => ({
  id: "aaaa-1111",
  username: "yuceann",
  display_name: "Yuceann",
  trust_stage: 3,
  trust_level_name: "Contributor",
  reputation_score: "78.00",
  ...overrides,
});

/** An `AnswerOut`. */
const answer = (overrides = {}) => ({
  id: "ans-1",
  body: "I used this quite a while ago and was incredibly happy with it.",
  is_best_answer: false,
  is_first_responder: false,
  helpful_votes: 0,
  created_at: "2026-09-01T00:00:00.000Z",
  responder: author({ id: "bbbb-2222", display_name: "Viole-nim", username: "viole" }),
  ...overrides,
});

/** A `QuestionDetailOut`. */
const question = (overrides = {}) => ({
  id: "q-1",
  product_id: "prod-1",
  product_name: "Jisulife Powerbank",
  body: "Is this good for traveling?",
  directed_to: "buyers",
  best_answer_id: null,
  answer_count: 1,
  created_at: "2026-08-30T00:00:00.000Z",
  asker: author(),
  answers: [answer()],
  ...overrides,
});

/* ------------------------------------------------------------ answer choice */

test("selectAnswer returns the explicitly selected answer", () => {
  const detail = question({
    answers: [answer({ id: "a" }), answer({ id: "b" }), answer({ id: "c" })],
  });
  assert.equal(selectAnswer(detail, "b").id, "b");
});

test("selectAnswer defaults to the accepted answer, not the first one", () => {
  // The asker's accepted answer is the one a moderator is looking for; falling
  // through to answers[0] would bury it behind whatever arrived first.
  const detail = question({
    best_answer_id: "c",
    answers: [answer({ id: "a" }), answer({ id: "b" }), answer({ id: "c", is_best_answer: true })],
  });
  assert.equal(selectAnswer(detail, null).id, "c");
});

test("selectAnswer falls back to the first answer when none is accepted", () => {
  const detail = question({ answers: [answer({ id: "a" }), answer({ id: "b" })] });
  assert.equal(selectAnswer(detail, null).id, "a");
});

test("selectAnswer falls back to the default when the selected id is stale", () => {
  // Switching questions keeps the old answer id in state for one render.
  const detail = question({ answers: [answer({ id: "a" })] });
  assert.equal(selectAnswer(detail, "gone").id, "a");
});

test("selectAnswer returns null for a question nobody has answered", () => {
  assert.equal(selectAnswer(question({ answers: [], answer_count: 0 }), null), null);
});

/* -------------------------------------------------------------- tab labels */

test("answerTabLabel names the responder", () => {
  assert.equal(answerTabLabel(answer(), 0), "Viole-nim");
});

test("answerTabLabel falls back to the username, then to an ordinal", () => {
  assert.equal(answerTabLabel(answer({ responder: author({ display_name: null }) }), 0), "yuceann");
  assert.equal(answerTabLabel(answer({ responder: null }), 2), "Answer 3");
});

test("answerTabLabel marks the accepted answer", () => {
  assert.equal(answerTabLabel(answer({ is_best_answer: true }), 0), "Viole-nim · Best");
});

/* ------------------------------------------------------------ author stats */

test("qaAuthorStats renders the trust score the Q&A schema actually carries", () => {
  const byLabel = Object.fromEntries(qaAuthorStats(author()).map((s) => [s.label, s]));
  assert.equal(byLabel["Trust Score"].available, true);
  assert.equal(byLabel["Trust Score"].value, "78");
});

test("qaAuthorStats marks age and review counts unavailable", () => {
  // `QAAuthor` carries id/username/display_name/trust_stage/trust_level_name/
  // reputation_score and nothing else — no created_at, no review counts. The
  // frame draws all four stats, so the three with no source say so.
  const byLabel = Object.fromEntries(qaAuthorStats(author()).map((s) => [s.label, s]));

  for (const label of ["Age", "Total Reviews", "Verified Reviews"]) {
    assert.equal(byLabel[label].available, false, `${label} has no source in QAAuthor`);
    assert.ok(byLabel[label].reason.length > 0);
  }
});

test("qaAuthorStats handles a question whose asker was deleted", () => {
  const byLabel = Object.fromEntries(qaAuthorStats(null).map((s) => [s.label, s]));
  assert.equal(byLabel["Trust Score"].available, false);
});

/* ----------------------------------------------------------------- photos */

test("answerPhotos is unavailable rather than an empty gallery", () => {
  // The frame draws a three-photo grid under the answer. No answers table,
  // schema or bucket stores an answer photo, so an empty grid would read as
  // "this responder attached none" instead of "we never collect them".
  const photos = answerPhotos();
  assert.equal(photos.available, false);
  assert.ok(photos.reason.length > 0);
});

/* ------------------------------------------------------------ question list */

test("questionRows searches the body, the product and the asker", () => {
  const rows = [
    question({ id: "a", body: "Is this good for traveling?" }),
    question({ id: "b", body: "Nothing alike", product_name: "Anker Zolo" }),
    question({ id: "c", body: "Nothing alike", product_name: "Other", asker: author({ display_name: "Viole-nim" }) }),
  ];

  assert.deepEqual(questionRows(rows, "TRAVELING").map((q) => q.id), ["a"]);
  assert.deepEqual(questionRows(rows, "anker").map((q) => q.id), ["b"]);
  assert.deepEqual(questionRows(rows, "viole").map((q) => q.id), ["c"]);
});

test("questionRows returns every row for an empty search", () => {
  const rows = [question({ id: "a" }), question({ id: "b" })];
  assert.deepEqual(questionRows(rows, "   ").map((q) => q.id), ["a", "b"]);
});

test("questionRows tolerates a question whose product and asker are missing", () => {
  const orphan = question({ id: "x", product_name: null, asker: null });
  assert.deepEqual(questionRows([orphan], "anything").map((q) => q.id), []);
  assert.deepEqual(questionRows([orphan], "").map((q) => q.id), ["x"]);
});

test("questionEmptyMessage distinguishes an outage from a truly empty queue", () => {
  assert.equal(questionEmptyMessage(null, 0), "Questions are temporarily unavailable.");
  assert.equal(questionEmptyMessage([], 0), "No questions have been asked yet.");
  assert.equal(questionEmptyMessage([question()], 0), "No question matches this search.");
});
