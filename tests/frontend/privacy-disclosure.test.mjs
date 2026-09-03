import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("../../app/privacy/page.tsx", import.meta.url), "utf8");

test("the policy discloses reading activity in plain words", () => {
  assert.match(SOURCE, /how long a review page is actively open/);
  assert.match(SOURCE, /changes at least every 24 hours/);
  assert.match(SOURCE, /not linked to any account/);
});

test("the policy states the reading-activity retention period", () => {
  assert.match(SOURCE, /Reading-activity records are deleted after 90 days/);
});

test("the disclosure claims no legal basis and no regulatory compliance", () => {
  const added = SOURCE.split("\n").filter((l) => /[Rr]eading activity|Reading-activity/.test(l)).join("\n");
  for (const forbidden of [/lawful basis/i, /legitimate interest/i, /complies with/i, /in compliance with/i, /GDPR/i]) {
    assert.ok(!forbidden.test(added), `disclosure must not assert: ${forbidden}`);
  }
});
