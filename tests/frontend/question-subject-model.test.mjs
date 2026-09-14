import assert from "node:assert/strict";
import test from "node:test";

import { answerByline, questionSubject } from "../../components/qa/question-subject-model.ts";

/**
 * A question is about a product or about a store, never both, and an answer is
 * from the store only when the store's claimed owner wrote it. Every Q&A
 * surface names the subject and the answerer through these two functions, so
 * a store question can never be labelled "Unnamed product" and a buyer's
 * answer can never wear the store's name.
 */

test("a product question is labelled with its product", () => {
  assert.deepEqual(
    questionSubject({ product_id: "p1", product_name: "Jisulife Life9", seller_id: null, seller_name: null }),
    { kind: "product", label: "Jisulife Life9", href: null },
  );
});

test("a store question is labelled with the store and links to its page", () => {
  assert.deepEqual(
    questionSubject({ product_id: null, product_name: null, seller_id: "s1", seller_name: "Jisulife Official Store" }),
    { kind: "seller", label: "Jisulife Official Store", href: "/sellers/s1" },
  );
});

test("a missing name falls back without inventing one", () => {
  assert.equal(
    questionSubject({ product_id: "p1", product_name: null, seller_id: null, seller_name: null }).label,
    "Unnamed product",
  );
  assert.equal(
    questionSubject({ product_id: null, product_name: null, seller_id: "s1", seller_name: null }).label,
    "Unnamed store",
  );
});

test("the store's own answer is shown under the store's name", () => {
  assert.deepEqual(
    answerByline({ is_seller_answer: true, seller_name: "Jisulife Official Store", responder: { username: "owner", display_name: null } }),
    { name: "Jisulife Official Store", seller: true },
  );
});

test("everyone else answers under their own name, even on a store question", () => {
  assert.deepEqual(
    answerByline({ is_seller_answer: false, seller_name: "Jisulife Official Store", responder: { username: "miguelito", display_name: null } }),
    { name: "miguelito", seller: false },
  );
  assert.deepEqual(
    answerByline({ is_seller_answer: false, seller_name: null, responder: null }),
    { name: "Former member", seller: false },
  );
});
