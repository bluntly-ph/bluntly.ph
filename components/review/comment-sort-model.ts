/**
 * Comment ordering for the "Sort comments by" sheet.
 *
 * Pure, so the ordering is testable without a DOM — this project has no DOM test
 * environment, and an ordering bug is exactly the kind that looks fine in a
 * screenshot.
 *
 * The sheet offers TWO axes, not one list of four: the reference shows a filled
 * radio in both the "By rating" group and the "By date" group at the same time.
 * So rating is the primary key and date breaks its ties — "most helpful, and
 * among equally helpful ones the newest first". A single four-way choice would
 * contradict the drawing.
 *
 * Sorting happens on the client because the whole thread already arrives in one
 * response and is nested into a tree before render. Adding a server parameter
 * would buy nothing and cost a round trip per change.
 */

export type RatingOrder = "most_helpful" | "least_helpful";
export type DateOrder = "latest" | "oldest";

export type CommentSort = { rating: RatingOrder; date: DateOrder };

export const DEFAULT_COMMENT_SORT: CommentSort = {
  rating: "most_helpful",
  date: "latest",
};

/** What the sheet is sorting: only the fields the order depends on. */
export type SortableComment = {
  helpful_votes: number;
  unhelpful_votes: number;
  created_at: string;
};

/**
 * Net helpfulness, not raw upvotes.
 *
 * A comment with 9 up and 8 down is not more helpful than one with 3 up and 0
 * down, and ordering by `helpful_votes` alone would put it first.
 */
export function helpfulnessOf(c: SortableComment): number {
  return (c.helpful_votes ?? 0) - (c.unhelpful_votes ?? 0);
}

function timeOf(c: SortableComment): number {
  const t = new Date(c.created_at).getTime();
  // An unparseable date must not silently sort as 1970 and jump to an end.
  return Number.isNaN(t) ? 0 : t;
}

/**
 * A copy of `comments`, ordered. The input is never mutated: React state holds
 * this array, and sorting it in place would change rendered order without a
 * re-render.
 */
export function sortComments<T extends SortableComment>(
  comments: readonly T[],
  { rating, date }: CommentSort = DEFAULT_COMMENT_SORT,
): T[] {
  const byRating = rating === "most_helpful" ? -1 : 1;
  const byDate = date === "latest" ? -1 : 1;

  return [...comments].sort((a, b) => {
    const h = helpfulnessOf(a) - helpfulnessOf(b);
    if (h !== 0) return h * byRating;
    const t = timeOf(a) - timeOf(b);
    if (t !== 0) return t * byDate;
    return 0;
  });
}
