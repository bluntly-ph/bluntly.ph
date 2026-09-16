import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

/**
 * The landing page's trust bullets must not promise something the product does
 * not do (BUG-032).
 *
 * The fourth bullet read "Every reviewer's earnings and history are public".
 * Earnings are private — to the reviewer and to moderators — and no public
 * surface shows them. A transparency claim that is false is a worse bug than a
 * missing bullet, and it is the kind that survives forever because it reads
 * well.
 *
 * Read from source rather than imported. `lib/landing-data.ts` pulls in two
 * dozen Phosphor icon modules, and importing it here took this file from
 * milliseconds to over two minutes — a suite nobody runs catches nothing.
 * The copy is what matters, and the copy is a string literal.
 */

const SOURCE = readFileSync(
  new URL("../../lib/landing-data.ts", import.meta.url),
  "utf8",
).replace(/\r/g, "");

/** `TRUST_POINTS`' bullet texts, in order, without the comments around them. */
function trustBulletTexts() {
  const start = SOURCE.indexOf("export const TRUST_POINTS");
  assert.ok(start >= 0, "TRUST_POINTS is gone from lib/landing-data.ts");
  const block = SOURCE.slice(start, SOURCE.indexOf("\n];", start));
  const code = block.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  return [...code.matchAll(/text:\s*\n?\s*"((?:[^"\\]|\\.)*)"/g)].map((m) =>
    m[1].replace(/\\'/g, "'").replace(/\\"/g, '"'),
  );
}

const APPROVED_FOURTH =
  "Seller ratings and reviewer track records are open for anyone to check.";

test("there are four trust bullets", () => {
  assert.equal(trustBulletTexts().length, 4);
});

test("the fourth bullet is the owner-approved copy", () => {
  assert.equal(trustBulletTexts()[3], APPROVED_FOURTH);
});

test("no bullet claims earnings are public", () => {
  // Deliberately broader than the one sentence that was wrong: the claim must
  // not come back in a paraphrase either.
  for (const text of trustBulletTexts()) {
    const lowered = text.toLowerCase();
    assert.ok(
      !(lowered.includes("earning") && lowered.includes("public")),
      `"${text}" claims earnings are public`,
    );
  }
});

test("no other copy in the module makes the same claim", () => {
  // The bullet was one instance; this catches a second copy elsewhere in the
  // landing data. Comments are stripped — the docblock above the fixed bullet
  // quotes the wrong sentence on purpose, to say what it replaced.
  const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.ok(!/earnings and history are public/i.test(code));
});

test("the bullets are distinct — the Figma frame's duplicate is not copied", () => {
  const texts = trustBulletTexts();
  assert.equal(new Set(texts).size, texts.length);
});
