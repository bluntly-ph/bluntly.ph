import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_SELLER_PHOTOS,
  MAX_SELLER_TITLE,
  MIN_SELLER_PROSE,
  contentBlocker,
  distributionBars,
  emptySellerDraft,
  missingDimension,
  percent,
  ratingPrompt,
  ratingWord,
  sellerInitials,
  toSellerReviewPayload,
} from "../../components/sellers/seller-model.ts";

/**
 * The seller surfaces state numbers about real stores, so the rules worth
 * locking are the honest ones: a store nobody has rated shows no rate at all
 * rather than "0%", and a rating is only sent once every FR-4 dimension has an
 * answer — where "not the same" and "missing item" are answers, not blanks.
 */

const full = () => ({
  ...emptySellerDraft(),
  overall: 4,
  recommend: true,
  service: 4,
  packaging: 5,
  accuracy: true,
  completeness: false,
  title: "Shipped my package securely",
  comment: "Came with so much bubble wrap.",
});

test("the limits follow the composer frames and the API", () => {
  assert.equal(MAX_SELLER_TITLE, 30);
  assert.equal(MIN_SELLER_PROSE, 15);
  assert.equal(MAX_SELLER_PHOTOS, 4);
});

test("a rate the API has no data for is shown as nothing, never 0%", () => {
  assert.equal(percent(null), null);
  assert.equal(percent(0), "0%");
  assert.equal(percent(0.755), "76%");
  assert.equal(percent(1), "100%");
});

test("the star bars run five to one and share the visible total", () => {
  const bars = distributionBars({ 1: 1, 2: 0, 3: 0, 4: 1, 5: 2 });
  assert.deepEqual(bars.map((b) => b.star), [5, 4, 3, 2, 1]);
  assert.deepEqual(bars.map((b) => b.count), [2, 1, 0, 0, 1]);
  assert.deepEqual(bars.map((b) => b.share), [0.5, 0.25, 0, 0, 0.25]);
});

test("an unrated store draws empty bars, not a division by zero", () => {
  const bars = distributionBars({ 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 });
  assert.ok(bars.every((b) => b.share === 0 && b.count === 0));
});

test("the breakdown reads string keys and fills absent stars, as JSON delivers them", () => {
  const bars = distributionBars({ "5": 3, "1": 1 });
  assert.equal(bars[0].count, 3);
  assert.equal(bars[1].count, 0);
  assert.equal(bars[4].count, 1);
});

test("the rating word needs a rating", () => {
  assert.equal(ratingWord(null), null);
  assert.equal(ratingWord(4.7), "Excellent");
  assert.equal(ratingWord(3.9), "Good");
  assert.equal(ratingWord(3.0), "Average");
  assert.equal(ratingWord(2.0), "Poor");
  assert.equal(ratingWord(1.0), "Bad");
});

test("a store without a logo is drawn with the initials of its first three words", () => {
  assert.equal(sellerInitials("Jisulife Authorized Store"), "JAS");
  assert.equal(sellerInitials("anker"), "A");
  assert.equal(sellerInitials("The Big Fan Shop Manila"), "TBF");
  assert.equal(sellerInitials("   "), "?");
});

test("the dimensions are asked for in the order they are drawn", () => {
  const order = [
    ["overall", 4],
    ["recommend", true],
    ["service", 3],
    ["packaging", 5],
    ["accuracy", true],
    ["completeness", true],
  ];
  const draft = emptySellerDraft();
  for (const [key, value] of order) {
    assert.equal(missingDimension(draft), key);
    draft[key] = value;
  }
  assert.equal(missingDimension(draft), null);
});

test("a negative answer is an answer", () => {
  const draft = { ...full(), recommend: false, accuracy: false, completeness: false };
  assert.equal(missingDimension(draft), null);
});

test("the written step needs a title and enough prose", () => {
  assert.equal(contentBlocker(full()), null);
  assert.match(contentBlocker({ ...full(), title: "   " }), /title/i);
  assert.match(contentBlocker({ ...full(), title: "x".repeat(31) }), /30/);
  assert.match(contentBlocker({ ...full(), comment: "x".repeat(14) }), /1 more character to go/);
  assert.match(contentBlocker({ ...full(), comment: "   short   " }), /10 more characters to go/);
});

test("the payload carries every dimension under the API's names", () => {
  assert.deepEqual(toSellerReviewPayload({ ...full(), photoUrls: ["https://x/1.jpg"] }), {
    overall_rating: 4,
    would_recommend: true,
    customer_service: 4,
    packaging_quality: 5,
    accuracy: true,
    order_completeness: false,
    title: "Shipped my package securely",
    comment: "Came with so much bubble wrap.",
    photo_urls: ["https://x/1.jpg"],
  });
});

test("an incomplete draft cannot become a payload", () => {
  assert.throws(() => toSellerReviewPayload(emptySellerDraft()), /overall/);
  assert.throws(() => toSellerReviewPayload({ ...full(), comment: "short" }), /character/);
});

test("the prompt after rating follows the stars given", () => {
  assert.equal(ratingPrompt(null), null);
  assert.match(ratingPrompt(5), /great/i);
  assert.match(ratingPrompt(4), /pretty good/i);
  assert.match(ratingPrompt(3), /mixed/i);
  assert.match(ratingPrompt(1), /sorry/i);
});
