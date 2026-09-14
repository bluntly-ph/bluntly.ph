import assert from "node:assert/strict";
import test from "node:test";

import {
  manilaToday,
  observationBlocker,
  observationPayload,
} from "../../components/reviews/price-capture-model.ts";

/**
 * "Report what you paid" — a price observation outside the composer.
 *
 * Unlike the composer's card, nothing here is optional: the form exists only
 * to file an observation, and the API needs an amount, a marketplace and a
 * date. The date is checked against the Philippine calendar, the same rule
 * the API applies (`PriceObservationIn._not_in_the_future`), so a buyer
 * reporting at 07:00 in Manila is not told their purchase is in the future.
 */

const TODAY = "2026-09-14";
const ok = { price: "1299.50", platform: "lazada", observedAt: "2026-09-10", variant: "" };

test("today is the Manila date, not the UTC one", () => {
  assert.equal(manilaToday(new Date("2026-09-13T16:30:00Z")), "2026-09-14");
  assert.equal(manilaToday(new Date("2026-09-13T15:59:00Z")), "2026-09-13");
});

test("a complete report has nothing blocking it", () => {
  assert.equal(observationBlocker(ok, TODAY), null);
});

test("the amount is required here, not a skip", () => {
  assert.match(observationBlocker({ ...ok, price: "" }, TODAY), /amount/i);
  assert.match(observationBlocker({ ...ok, price: "0" }, TODAY), /amount/i);
});

test("the marketplace is required", () => {
  assert.match(observationBlocker({ ...ok, platform: null }, TODAY), /where/i);
});

test("the date is required and cannot be after today in Manila", () => {
  assert.match(observationBlocker({ ...ok, observedAt: "" }, TODAY), /date/i);
  assert.match(observationBlocker({ ...ok, observedAt: "2026-09-15" }, TODAY), /future/i);
  assert.equal(observationBlocker({ ...ok, observedAt: TODAY }, TODAY), null);
});

test("a variant is optional and bounded at the API's 120 characters", () => {
  assert.match(observationBlocker({ ...ok, variant: "x".repeat(121) }, TODAY), /120/);
  assert.equal(observationBlocker({ ...ok, variant: "  Blue, 256 GB  " }, TODAY), null);
});

test("the payload keeps the price as a decimal string and trims the variant", () => {
  assert.deepEqual(observationPayload({ ...ok, variant: "  Blue, 256 GB  " }), {
    platform: "lazada",
    price: "1299.50",
    observed_at: "2026-09-10",
    variant: "Blue, 256 GB",
  });
  assert.equal(observationPayload(ok).variant, null);
});
