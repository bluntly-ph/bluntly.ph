import assert from "node:assert/strict";
import test from "node:test";

import { showsTrustBadge } from "../../components/review/trust-badge-model.ts";

/**
 * The public trust badge follows the API's `has_trust_badge` (proof + checks +
 * moderation, completion contract X.2) and nothing else. It fails closed: a
 * response from a build that does not send the field shows no badge, rather
 * than falling back to the photo-only `verification_status` it replaced.
 */

test("the badge shows when the API grants it", () => {
  assert.equal(showsTrustBadge({ has_trust_badge: true, verification_status: "verified" }), true);
});

test("a verified photo alone is not the badge", () => {
  assert.equal(showsTrustBadge({ has_trust_badge: false, verification_status: "verified" }), false);
});

test("an older response without the field shows no badge", () => {
  assert.equal(showsTrustBadge({ verification_status: "verified" }), false);
  assert.equal(showsTrustBadge(null), false);
});
