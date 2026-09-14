import assert from "node:assert/strict";
import test from "node:test";

import { externalCheckLabel } from "../../components/admin/review-queue-model.ts";

/**
 * FR-8 layers 2 and 3 have no provider. The queue card must say so, and must
 * never read as a pass for a status it does not recognise or did not receive.
 */

test("a check with no provider says so", () => {
  assert.deepEqual(externalCheckLabel("not_configured"), { label: "No provider", ran: false });
});

test("a card from an older API without the field reads as no provider, not clear", () => {
  assert.deepEqual(externalCheckLabel(undefined), { label: "No provider", ran: false });
});

test("an unknown status fails closed", () => {
  assert.deepEqual(externalCheckLabel("pending"), { label: "No provider", ran: false });
});

test("results a provider could return are named plainly", () => {
  assert.deepEqual(externalCheckLabel("clear"), { label: "No match found", ran: true });
  assert.deepEqual(externalCheckLabel("flagged"), { label: "Match found", ran: true });
});
