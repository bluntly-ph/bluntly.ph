/**
 * The star rating colour ladder, from Figma "Icon/Star" (6805:431): a filled
 * star takes the colour of the rating it belongs to — the file's cards draw two
 * stars coral, three yellow, four and five green. Unfilled stars stay grey.
 *
 * One helper so the composers' rating inputs and the read-only star rows grade
 * the same value the same way.
 */
export const STAR_EMPTY = "var(--base-gray-400)";

export function starColor(rating: number | null | undefined): string {
  if (rating == null || !Number.isFinite(rating)) return STAR_EMPTY;
  const rounded = Math.round(rating);
  if (rounded < 1) return STAR_EMPTY;
  if (rounded <= 2) return "var(--brand-coral)";
  if (rounded === 3) return "var(--semantic-star)";
  return "var(--semantic-success-500)";
}

/**
 * Ratings are 0 to 5 in half steps (owner requirement, 2026-09-16), so a star
 * row draws three states. `position` is the star's place, 1 to 5.
 *
 * A value of 2.5 fills stars 1 and 2, half-fills star 3 and leaves the rest
 * empty. Anything between steps is judged by the nearer half, so a stale whole
 * number and a fresh half both render sensibly.
 */
export type StarFill = "full" | "half" | "empty";

export function starFill(position: number, value: number | null | undefined): StarFill {
  if (value == null || !Number.isFinite(value) || value <= 0) return "empty";
  const stepped = Math.round(value * 2) / 2;
  if (stepped >= position) return "full";
  if (stepped >= position - 0.5) return "half";
  return "empty";
}

/** The steps a rating control offers: 0, 0.5, 1 … 5. */
export const STAR_STEPS = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5] as const;

/** 0 is a real answer, so "has the reader answered?" cannot be `Boolean(value)`. */
export function hasRating(value: number | null | undefined): boolean {
  return value != null && Number.isFinite(value);
}

/** One decimal for a half, none for a whole star: 4.5 and 4, never 4.0. */
export function formatRating(value: number | null | undefined): string {
  if (!hasRating(value)) return "—";
  const stepped = Math.round((value as number) * 2) / 2;
  return Number.isInteger(stepped) ? String(stepped) : stepped.toFixed(1);
}

