import assert from "node:assert/strict";
import test from "node:test";

import {
  PRICE_PLATFORMS,
  normalisePrice,
  priceBlocker,
  pricePayload,
} from "../../components/reviews/price-capture-model.ts";

/**
 * "Let's talk money" feeds the community price panel. A price observation is
 * a price AND the marketplace it was paid on, so the card now asks for both —
 * but only once a price is typed. Skipping stays one press, as the frame draws
 * it, and a marketplace picked with no price is not an observation.
 */

test("the marketplaces offered are the API's platforms", () => {
  assert.deepEqual([...PRICE_PLATFORMS], ["shopee", "lazada", "amazon", "other"]);
});

test("a blank price needs nothing: skipping is still one press", () => {
  assert.equal(priceBlocker("", null), null);
  assert.equal(priceBlocker("   ", "shopee"), null);
});

test("a price needs the marketplace it was paid on", () => {
  assert.match(priceBlocker("499", null), /where/i);
  assert.equal(priceBlocker("499", "lazada"), null);
});

test("an amount that is not a positive number is refused", () => {
  assert.match(priceBlocker("0", "shopee"), /amount/i);
  assert.match(priceBlocker(".", "shopee"), /amount/i);
});

test("an amount beyond what the API records is refused", () => {
  assert.match(priceBlocker("10000001", "shopee"), /check the amount/i);
  assert.equal(priceBlocker("10000000", "shopee"), null);
});

test("typing is cleaned to digits, one decimal point, and centavos", () => {
  assert.equal(normalisePrice("₱1,299.505"), "1299.50");
  assert.equal(normalisePrice("12.3.4"), "12.34");
  assert.equal(normalisePrice("abc"), "");
});

test("the payload sends a price and its marketplace together, or neither", () => {
  assert.deepEqual(pricePayload("", "shopee"), { price_paid: null, price_platform: null });
  assert.deepEqual(pricePayload("499", "lazada"), { price_paid: 499, price_platform: "lazada" });
  assert.deepEqual(pricePayload("499", null), { price_paid: 499, price_platform: null });
});
