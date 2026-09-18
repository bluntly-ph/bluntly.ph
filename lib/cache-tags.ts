/**
 * Cache tags for the public review read models, and which writes expire them.
 *
 * Public review reads are kept in Next's Data Cache for 60 seconds (signed-out
 * reads only — lib/api/client.ts never caches a credentialed response). Nothing
 * expired them after a write, so on 2026-09-18 an upvote committed at once and
 * the API returned the new count, while the review page and every card that
 * showed it kept serving the old count for a minute and one more request
 * (production probe: 0 -> vote -> still 0 at +65 s -> 1 on the next request).
 *
 * Two tags, because a write to one review changes two kinds of read:
 *
 *   review:<id>   that review's own reads: its detail and its comments
 *   review-lists  every list a review card can appear in — feed, search,
 *                 landing, categories, public profiles — since a card carries
 *                 the review's counts and any list may hold it
 *
 * The BFF (app/api/bff/[...path]/route.ts) expires them after a successful
 * write, so a mutation invalidates only the review read models, and caching
 * stays on for everything else.
 */

export const REVIEW_LISTS = "review-lists";

export function reviewTag(id: string): string {
  return `review:${id}`;
}

const UUID = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";

/** A write to one review: vote, comment, edit, report, or a moderator decision. */
const REVIEW_WRITE = new RegExp(`^api/v1/(?:admin/)?reviews/(${UUID})(?:/|$)`);

/** A moderator's report decision, which can take a review down. */
const REPORT_DECISION = new RegExp(`^api/v1/admin/reports/${UUID}/decision$`);

/**
 * The tags to expire after a successful BFF request, or none.
 *
 * `path` is the BFF path without a leading slash (`api/v1/reviews/<id>/vote`).
 * Reads never expire anything. A report decision names its review only in the
 * response body, so the caller passes that id as `reportedReviewId`.
 */
export function tagsToExpire(
  method: string,
  path: string,
  reportedReviewId?: string | null,
): string[] {
  if (method === "GET" || method === "HEAD") return [];
  const review = REVIEW_WRITE.exec(path);
  if (review) return [reviewTag(review[1].toLowerCase()), REVIEW_LISTS];
  if (REPORT_DECISION.test(path)) {
    return reportedReviewId ? [reviewTag(reportedReviewId.toLowerCase()), REVIEW_LISTS] : [REVIEW_LISTS];
  }
  return [];
}

/** True for a path whose response must be read to find the review it touched. */
export function isReportDecision(path: string): boolean {
  return REPORT_DECISION.test(path);
}
