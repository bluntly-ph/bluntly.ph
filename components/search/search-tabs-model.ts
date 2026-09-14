/** Which set of results /search is showing. */
export type SearchTab = "reviews" | "questions" | "sellers";

/**
 * The review orders the feed serves (GET /reviews/feed `sort`): most helpful —
 * a Wilson lower bound on helpful votes, and the default — and latest.
 */
export type ReviewSort = "wilson" | "newest";

export const DEFAULT_REVIEW_SORT: ReviewSort = "wilson";

/** A `?sort=` value from the URL, narrowed to an order the feed serves. */
export function parseReviewSort(raw: string | undefined): ReviewSort {
  return raw === "newest" ? "newest" : DEFAULT_REVIEW_SORT;
}

/**
 * The href for a tab, preserving the reader's context across the switch.
 *
 * Exported so the rules are testable without a DOM: the query follows the reader
 * to the other tab, `reviews` is the default and so carries no `tab` parameter,
 * and a category or review order is NOT carried to questions or sellers — they
 * narrow reviews and mean nothing there, so passing one would put a filter in
 * the URL that silently does nothing. The default order is left out too, so the
 * plain URL stays the canonical one.
 */
export function searchTabHref(
  tab: SearchTab,
  {
    q,
    category,
    sort,
    from,
  }: { q?: string; category?: string; sort?: ReviewSort; from?: string } = {},
): string {
  const params = new URLSearchParams();
  if (q?.trim()) params.set("q", q);
  if (tab === "reviews") {
    if (category) params.set("category", category);
    if (sort && sort !== DEFAULT_REVIEW_SORT) params.set("sort", sort);
  } else {
    params.set("tab", tab);
  }
  if (from) params.set("from", from);
  const qs = params.toString();
  return `/search${qs ? `?${qs}` : ""}`;
}

/**
 * Where clearing the category goes. A visitor who arrived from /categories goes
 * back there rather than being stranded on an unfiltered /search (BUG-011);
 * anyone else keeps their query and order with the category dropped.
 */
export function clearCategoryHref({
  q,
  sort,
  from,
}: {
  q?: string;
  sort?: ReviewSort;
  from?: string;
}): string {
  if (from === "categories") return "/categories";
  return searchTabHref("reviews", { q, sort, from });
}
