import assert from "node:assert/strict";
import test from "node:test";

import {
  READER_COOKIE_MAX_AGE,
  READER_COOKIE_NAME,
  mintReaderId,
  validReaderId,
} from "../../lib/reader-id-policy.ts";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

test("minted reader identifiers are random UUIDv4 values", () => {
  const values = new Set(Array.from({ length: 64 }, () => mintReaderId()));

  assert.equal(values.size, 64);
  for (const value of values) assert.match(value, UUID_V4);
});

test("reader identity policy is 24 hours and first party", () => {
  assert.equal(READER_COOKIE_NAME, "bluntly_rid");
  assert.equal(READER_COOKIE_MAX_AGE, 86_400);
});

test("hardware and network inputs are not accepted by the minting API", () => {
  assert.equal(mintReaderId.length, 0);
});

test("reader identifiers accept only canonical UUIDv4 values", () => {
  assert.equal(validReaderId("9403e48c-7a4a-4c5c-8c84-4d5a64fc8bc7"), true);
  assert.equal(validReaderId("9403e48c-7a4a-3c5c-8c84-4d5a64fc8bc7"), false);
  assert.equal(validReaderId("9403e48c-7a4a-4c5c-7c84-4d5a64fc8bc7"), false);
  assert.equal(validReaderId("9403e48c7a4a4c5c8c844d5a64fc8bc7"), false);
  assert.equal(validReaderId(undefined), false);
});
