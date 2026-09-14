import assert from "node:assert/strict";
import test from "node:test";

import { SIMULATED_RAILS, simulationHeadline } from "../../components/dashboard/payout-simulation-model.ts";

/**
 * The simulated GCash / Maya payout preview (completion contract X.4). The
 * headline is the part a reviewer reads first, so it must say "would" and name
 * the rail — never read like money that has moved.
 */

test("the two simulated rails, as the API names them", () => {
  assert.deepEqual(SIMULATED_RAILS.map((r) => r.value), ["gcash", "maya"]);
  assert.deepEqual(SIMULATED_RAILS.map((r) => r.label), ["GCash", "Maya"]);
});

test("an eligible preview says what would happen, in the conditional", () => {
  const line = simulationHeadline({ rail: "gcash", eligible: true, amount: "1200.75", short_by: "0.00" });
  assert.match(line, /would/i);
  assert.match(line, /GCash/);
  assert.match(line, /₱1,200\.75/);
});

test("an ineligible preview says how far off the minimum it is", () => {
  const line = simulationHeadline({ rail: "maya", eligible: false, amount: "0.00", short_by: "87.50" });
  assert.match(line, /₱87\.50/);
  assert.match(line, /minimum/i);
  assert.doesNotMatch(line, /would be paid/i);
});
