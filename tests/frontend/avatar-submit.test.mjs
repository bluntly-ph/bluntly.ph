import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

/**
 * The avatar has to be in the form when the form is submitted (BUG-028).
 *
 * QA: "Uploaded avatar appears initially but is not reflected after refreshing
 * the page." It appeared because the preview is a local `blob:` URL. It did not
 * persist because the photo never left the browser: the `<input type="file">`
 * lived inside step 1, the wizard submits on step 4, and an unmounted input
 * contributes nothing to a FormData. Nothing errored. `users.avatar_url` was
 * null for all 18 accounts in production.
 *
 * The specific trap is that the code LOOKED right — there was a ref, and a
 * DataTransfer copy onto it, sitting in `finishIntro` where you would want it.
 * The ref just pointed at an element that no longer existed.
 *
 * Read from source, like the other JSX guards here: the failure is structural
 * (which element is mounted when), and that is visible in the markup.
 */

const SOURCE = readFileSync(
  new URL("../../app/onboarding/OnboardingWizard.tsx", import.meta.url),
  "utf8",
).replace(/\r/g, "");

/** The wizard's `<form>` body, minus anything inside a `step === n` branch. */
function formLevelMarkup() {
  const start = SOURCE.indexOf("<form");
  assert.ok(start >= 0, "the wizard has no form");
  const body = SOURCE.slice(start);
  // Everything from the first step branch onward is conditionally mounted.
  const firstBranch = body.indexOf("{step === 1 ?");
  assert.ok(firstBranch > 0, "the step branches are no longer recognisable");
  return body.slice(0, firstBranch);
}

test("exactly one input is named avatar", () => {
  // Two would mean the picker is also submitting, and which one wins is then a
  // question about mount order rather than a decision anyone made.
  const named = [...SOURCE.matchAll(/name="avatar"/g)];
  assert.equal(named.length, 1);
});

test("the avatar input is mounted at form level, not inside a step", () => {
  assert.match(
    formLevelMarkup(),
    /name="avatar"/,
    "the avatar input is inside a step branch, so it is gone by the time the form submits",
  );
});

test("it sits with the other fields that outlive their step", () => {
  const form = formLevelMarkup();
  for (const field of ["username", "display_name", "interests"]) {
    assert.match(form, new RegExp(`name="${field}"`), `${field} is no longer form-level`);
  }
});

test("the file is copied into that input before the last step", () => {
  // `finishIntro` runs on both routes into step 4 — Continue and Skip — so the
  // copy has to happen there and has to target the submit input.
  const finish = SOURCE.slice(
    SOURCE.indexOf("function finishIntro"),
    SOURCE.indexOf("function goBack"),
  );
  assert.ok(finish.length > 0, "finishIntro is gone");
  assert.match(finish, /copyAvatarIntoTheForm\(\)/);

  const copy = SOURCE.slice(
    SOURCE.indexOf("function copyAvatarIntoTheForm"),
    SOURCE.indexOf("return (", SOURCE.indexOf("function copyAvatarIntoTheForm")),
  );
  assert.match(copy, /submitFileRef\.current/, "the copy targets the wrong ref");
  assert.match(copy, /DataTransfer/);
  assert.ok(
    !/fileRef\.current\.files\s*=/.test(copy),
    "the copy writes to the step-1 picker, which is unmounted by then",
  );
});

test("the picker stays reachable by keyboard and the submit input does not", () => {
  // The visible control is step 1's button plus its picker; the form-level
  // input is plumbing. Two tab stops for one photo is a worse experience than
  // one, and a hidden file input in the tab order reads as an unlabelled
  // control to a screen reader.
  const form = formLevelMarkup();
  const input = form.slice(form.indexOf('name="avatar"') - 300, form.indexOf('name="avatar"') + 300);
  assert.match(input, /tabIndex=\{-1\}/);
  assert.match(input, /aria-hidden="true"/);
});
