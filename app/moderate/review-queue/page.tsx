import type { Metadata } from "next";

import { ReviewQueueScreen } from "@/components/admin/ReviewQueueScreen";
import {
  isTab,
  parseQueueFilters,
  queueApiQuery,
  type Tab,
} from "@/components/admin/review-queue-model";
import { getQueue, getReports } from "@/lib/moderation";
import { getQuestions } from "@/lib/qa";

export const metadata: Metadata = {
  title: "Review queue — bluntly admin",
};

/**
 * The Review Queue's own route.
 *
 * The URL carries the whole question: which tab, and which slice of the
 * backlog. `tab` lets the Overview's Queue Breakdown and the header's overdue
 * badge link straight to a filtered queue, and lets a moderator share the view
 * they are looking at.
 *
 * The queue itself is filtered, ordered and paginated SERVER-side against the
 * whole backlog (`referral_service.get_prioritized_queue`). This page validates
 * the URL against the policy's own vocabulary and forwards nothing else — a
 * hand-edited `?band=critical` narrows to "no band filter" rather than putting
 * a 422 on a moderator's screen.
 *
 * The frames this screen was built to were deleted from the Figma file on
 * 2026-09-09 and replaced by a single 1280x1943 "Admin Page - Review Queue"
 * (6922:837); the layout here is still the old one, and the re-layout is its
 * own piece of work.
 */
export default async function ReviewQueuePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const first = (value: string | string[] | undefined) =>
    Array.isArray(value) ? (value[0] ?? "") : (value ?? "");

  const search = new URLSearchParams();
  for (const key of ["band", "lane", "sla", "factor", "q", "limit", "offset"]) {
    const value = first(params[key]);
    if (value) search.set(key, value);
  }
  const filters = parseQueueFilters(search);

  const rawTab = first(params.tab);
  const tab: Tab = isTab(rawTab) ? rawTab : "reviews";

  // The Answers tab reads the public Q&A endpoints. There is no `/admin` Q&A
  // route and this needs none: `GET /questions` already returns the asker,
  // the answer count and the trust of everyone involved, and the per-question
  // detail is fetched through the BFF only for the row a moderator opens.
  // `getQuestions` returns null when the API is unreachable — a failing Q&A
  // list must not blank the review queue, same defence as `getReports`. That
  // null is passed THROUGH rather than flattened to []: an outage and an empty
  // queue are different facts, and the tab says which one it is. `getQueue`
  // now answers the same way, with a discriminated result.
  const [queue, reports, questions] = await Promise.all([
    getQueue(queueApiQuery(filters)),
    getReports(),
    getQuestions(),
  ]);

  return (
    <ReviewQueueScreen
      queue={queue}
      filters={filters}
      reports={reports}
      questions={questions}
      initialTab={tab}
      now={queue.fetchedAt}
    />
  );
}
