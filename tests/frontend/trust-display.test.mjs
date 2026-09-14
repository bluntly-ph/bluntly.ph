import assert from "node:assert/strict";
import test from "node:test";

import { TRUST_LEVEL_NAMES, trustLevel, trustLevelName } from "../../lib/trust.ts";

/**
 * The frontend shows the trust level the backend computed, never a decorative
 * one (completion contract §9, matrix 7.8).
 *
 * The level name is a database expression on `users.trust_level_name`; these
 * names are pinned in the same order by `backend/tests/test_trust_level_names.py`,
 * so a rename on either side fails a test on that side. Copy that refers to a
 * level ("become a Verified Buyer") reads the name from here instead of typing it.
 */

test("the six levels, in stage order, as the backend names them", () => {
  assert.deepEqual([...TRUST_LEVEL_NAMES], [
    "Newcomer",
    "Contributor",
    "Verified Buyer",
    "Established Reviewer",
    "Trusted Reviewer",
    "Community Expert",
  ]);
});

test("a stage number reads as its level name", () => {
  assert.equal(trustLevelName(0), "Newcomer");
  assert.equal(trustLevelName(2), "Verified Buyer");
  assert.equal(trustLevelName(5), "Community Expert");
  assert.equal(trustLevelName(9), null);
  assert.equal(trustLevelName(null), null);
});

test("the badge prefers the API's name and falls back to the stage", () => {
  assert.equal(trustLevel("Trusted Reviewer", 4), "Trusted Reviewer");
  assert.equal(trustLevel("  ", 3), "Stage 3");
  assert.equal(trustLevel(null, null), "Stage 0");
});
