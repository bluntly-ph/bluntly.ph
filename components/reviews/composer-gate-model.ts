/**
 * What each composer step requires before Continue lights up, and what the
 * counter says while it does not.
 *
 * Split out of WriteReviewForm so the frames' contract is testable without a
 * DOM — the form is .tsx and the frontend runner cannot import JSX.
 *
 * Every number here is read off the reviewer pack rather than chosen:
 *
 *   step 1  "Reviewer Page - Step 1.1.png" counts down "30 characters
 *           remaining" and greys Continue; "1.2.png" swaps to "Solid review!"
 *           in orange and turns Continue on. So 30 is a floor.
 *   step 5  the same control and the same floor, with "I'm sure someone will
 *           appreciate this" as the satisfied line ("Step 5.png" / "5.1.png").
 *   step 6  "Step 6.png" greys Continue with no photo and "6.1.png" turns it
 *           orange with one, so the photo gates the step — and the frame puts
 *           a Skip link under the card as the way past it.
 *   step 7  "0/30 characters", so the title is capped at 30. The API accepts
 *           1..200; this is the tighter client limit the frame draws.
 */

export const MIN_PROSE = 30;
export const MAX_TITLE = 30;

export type GateDraft = {
  discussion: string;
  verdict: string | null;
  /** null until answered. 0 is an answer (owner requirement, 2026-09-16). */
  rating: number | null;
  pros: string;
  cons: string;
  anti: string;
  photoUrl: string | null;
  title: string;
  /** Disclosure of a material relationship (X.1); "none" is an answer. */
  disclosure: string | null;
};

/** How many characters short of the floor a field still is. Never negative. */
export function remaining(value: string, min: number = MIN_PROSE): number {
  return Math.max(0, min - value.trim().length);
}

/**
 * The line under a prose field: the countdown, or the step's own encouragement.
 * Two different sentences in the pack, so the satisfied one is passed in.
 */
export function counterLabel(value: string, satisfied: string): string {
  const left = remaining(value);
  return left > 0 ? `${left} characters remaining` : satisfied;
}

/** Whether that line is the orange one. */
export function counterIsSatisfied(value: string): boolean {
  return remaining(value) === 0;
}

/** Non-empty lines, the shape pros/cons are stored in. */
function lines(value: string): string[] {
  return value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Why Continue is disabled on `step`, or null when it is not.
 *
 * Steps are 0-based, matching the form; the frames number them 1-7.
 */
export function blockerFor(step: number, draft: GateDraft): string | null {
  switch (step) {
    case 0:
      return remaining(draft.discussion) > 0
        ? "Write at least a couple of sentences about your experience."
        : null;
    case 1:
      return draft.verdict ? null : "Pick a verdict.";
    case 2:
      return draft.rating !== null ? null : "Give it a star rating.";
    case 3:
      return lines(draft.pros).length === 0 || lines(draft.cons).length === 0
        ? "Give at least one pro and one con — both are required."
        : null;
    case 4:
      return remaining(draft.anti) > 0
        ? "Say who should skip this one, in a sentence or so."
        : null;
    case 5:
      return draft.photoUrl ? null : "Add a photo, or skip this step.";
    case 6:
      if (!draft.title.trim()) return "Give your review a title.";
      // INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY: step 7's frame
      // draws the title only; disclosure (X.1) must be answered before submit.
      return draft.disclosure
        ? null
        : "Say whether you received anything for this review or are connected to the brand.";
    default:
      return null;
  }
}

/** The button's label. Only the last step submits. */
export function buttonLabel(step: number, stepCount: number, busy: boolean): string {
  if (busy) return "Submitting…";
  return step === stepCount - 1 ? "Submit" : "Continue";
}
