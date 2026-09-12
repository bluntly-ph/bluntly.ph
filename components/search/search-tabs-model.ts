/** Which set of results /search is showing. */
export type SearchTab = "reviews" | "questions";

/**
 * The href for a tab, preserving the reader's context across the switch.
 *
 * Exported so the rules are testable without a DOM: the query follows the reader
 * to the other tab, `reviews` is the default and so carries no `tab` parameter,
 * and a category is NOT carried to questions — categories narrow reviews and
 * mean nothing there, so passing one would put a filter in the URL that silently
 * does nothing.
 */
export function searchTabHref(
  tab: SearchTab,
  { q, category, from }: { q?: string; category?: string; from?: string } = {},
): string {
  const params = new URLSearchParams();
  if (q?.trim()) params.set("q", q);
  if (category && tab === "reviews") params.set("category", category);
  if (tab !== "reviews") params.set("tab", tab);
  if (from) params.set("from", from);
  const qs = params.toString();
  return `/search${qs ? `?${qs}` : ""}`;
}
