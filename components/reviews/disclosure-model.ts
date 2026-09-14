/**
 * Disclosure of a material relationship (completion contract X.1).
 *
 * A reviewer says whether they bought the product themselves, got it free or
 * discounted, or are connected to the brand or seller. Readers see the last two
 * on the review. "No" shows nothing — it is the ordinary case — and a review
 * written before the question existed (`null`) shows nothing either, rather
 * than being labelled with an answer its author never gave.
 */

export type MaterialRelationship = "none" | "free_or_discounted" | "connected";

export const DISCLOSURE_OPTIONS: readonly { value: MaterialRelationship; label: string }[] = [
  { value: "none", label: "No, I bought it myself" },
  { value: "free_or_discounted", label: "I got it free or discounted" },
  { value: "connected", label: "I work for or am connected to the brand or seller" },
];

/** What readers see on the review, or null when there is nothing to disclose. */
export function disclosureLabel(value: MaterialRelationship | null | undefined): string | null {
  if (value === "free_or_discounted") return "Reviewer got this free or discounted";
  if (value === "connected") return "Reviewer is connected to the brand or seller";
  return null;
}
