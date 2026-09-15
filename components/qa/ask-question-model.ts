/**
 * The words of a question and the specifics its asker wants answered.
 *
 * "Question Page - Step 2" (4695:14599) asks "Are there any specifics you'd
 * like to know?" and the Question Page (4218:1856) shows the answer as
 * "Requirements:" tags. The API stores only the question's body, so the chosen
 * specifics travel as its last line — "Looking for: Experience, Rating" —
 * which reads naturally to anyone answering, and is read back here into tags.
 * Only an exact line of known specifics is taken back out; anything else stays
 * part of what the asker wrote.
 */

export const QUESTION_REQUIREMENTS = [
  "Experience",
  "Pros & Cons",
  "Do you recommend this?",
  "Is this right for me?",
  "Rating",
] as const;

export type QuestionRequirement = (typeof QUESTION_REQUIREMENTS)[number];

/** "15 characters remaining" on the empty field in the frame. */
export const MIN_QUESTION_CHARS = 15;
/** The API takes 2000; the rest is room for the specifics line. */
export const MAX_QUESTION_TEXT = 1800;

const PREFIX = "Looking for: ";

function isRequirement(value: string): value is QuestionRequirement {
  return (QUESTION_REQUIREMENTS as readonly string[]).includes(value);
}

export function composeQuestionBody(text: string, requirements: readonly QuestionRequirement[]): string {
  const words = text.trim();
  const chosen = QUESTION_REQUIREMENTS.filter((r) => requirements.includes(r));
  return chosen.length > 0 ? `${words}\n\n${PREFIX}${chosen.join(", ")}` : words;
}

export function splitQuestionBody(body: string): { text: string; requirements: QuestionRequirement[] } {
  const cut = body.lastIndexOf("\n");
  const last = cut === -1 ? "" : body.slice(cut + 1);
  if (!last.startsWith(PREFIX)) return { text: body, requirements: [] };
  const items = last.slice(PREFIX.length).split(", ");
  if (items.length === 0 || !items.every(isRequirement)) return { text: body, requirements: [] };
  return { text: body.slice(0, cut).trimEnd(), requirements: items as QuestionRequirement[] };
}
