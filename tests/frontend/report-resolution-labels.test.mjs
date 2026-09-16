import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { REPORT_RESOLUTION_LABELS } from "../../components/admin/review-queue-model.ts";

/**
 * The four report outcomes (owner §30, 2026-09-16).
 *
 * The moderator console writes one of these values to
 * `POST /admin/reports/{id}/decision` and reads it back on a closed report, so
 * the two sides have to agree on the vocabulary. The backend enum is the
 * authority; this pins the frontend copy of it against that file, the way
 * `trust-display.test.mjs` pins the trust level names.
 */

const BACKEND_ENUM = readFileSync(
  new URL("../../backend/app/models/enums.py", import.meta.url),
  "utf8",
).replace(/\r/g, "");

/** The member lines of `class ReportResolution`, in declaration order. */
function backendResolutions() {
  const start = BACKEND_ENUM.indexOf("class ReportResolution");
  assert.ok(start >= 0, "ReportResolution is missing from the backend enums");
  const body = BACKEND_ENUM.slice(start, BACKEND_ENUM.indexOf("\nclass ", start + 1));
  return [...body.matchAll(/^\s{4}(\w+) = "(\w+)"$/gm)].map((m) => m[2]);
}

test("the console labels exactly the outcomes the backend can return", () => {
  assert.deepEqual(Object.keys(REPORT_RESOLUTION_LABELS).sort(), backendResolutions().sort());
});

test("every label says what happened to the content, not just that it closed", () => {
  for (const [value, label] of Object.entries(REPORT_RESOLUTION_LABELS)) {
    assert.ok(label.length > 0, `${value} has no label`);
    assert.ok(
      label.length > value.length,
      `${value} is labelled with its own enum value rather than a sentence`,
    );
  }
});

test("the labels are distinct — two outcomes must not read the same", () => {
  const labels = Object.values(REPORT_RESOLUTION_LABELS);
  assert.equal(new Set(labels).size, labels.length);
});

test("the two content outcomes name the direction they moved the review", () => {
  assert.match(REPORT_RESOLUTION_LABELS.content_removed, /unpublish/i);
  assert.match(REPORT_RESOLUTION_LABELS.content_restored, /publish/i);
});
