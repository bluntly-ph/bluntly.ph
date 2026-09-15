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
