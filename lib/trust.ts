/**
 * How a reviewer's trust is written on screen (BUG-004).
 *
 * The badge is a level *name* plus a number, and it has to be both. The name
 * alone is not a score — stage 2 is called "Verified Buyer", which is exactly
 * why QA read the old badge as a hardcoded label. The number alone is not
 * meaningful either: 62 says nothing about what the reviewer has earned.
 *
 * Defined once because the badge appears on six surfaces — the featured card,
 * a review, a public profile, your own profile, a Q&A answer, and a comment —
 * and a trust indicator that reads differently depending on where you found it
 * is worse than one that is merely plain.
 *
 * Not a client component: this is pure formatting, so it stays importable from
 * both server and client trees.
 */

/** Reputation is 0..100 (ADR-003), and arrives as a string decimal over JSON. */
export function trustScore(
  raw: string | number | null | undefined,
): number | null {
  if (raw === null || raw === undefined || raw === "") return null;
  const n = typeof raw === "string" ? Number(raw) : raw;
  // Rounded: a trust badge reading "62.00" implies a precision the formula
  // does not have, and the decimals are never what the reader is asking about.
  return Number.isFinite(n) ? Math.round(n) : null;
}

/** The level name, falling back to the stage when a name is somehow missing. */
export function trustLevel(
  levelName: string | null | undefined,
  stage: number | null | undefined,
): string {
  return levelName?.trim() || `Stage ${stage ?? 0}`;
}

/**
 * The spoken form, for `aria-label` and `title`.
 *
 * Sighted readers get "Verified Buyer · 62", which is compact but relies on the
 * separator carrying meaning. A screen reader should hear the relationship
 * spelled out, and "out of 100" is the part that makes 62 interpretable at all.
 */
export function trustDescription(level: string, score: number | null): string {
  return score === null
    ? level
    : `${level}, trust score ${score} out of 100`;
}
