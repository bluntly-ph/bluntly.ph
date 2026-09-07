import type { Metadata } from "next";

import { ReviewQueueScreen } from "@/components/admin/ReviewQueueScreen";
import { getQueue, getReports } from "@/lib/moderation";
import { getQuestions } from "@/lib/qa";

export const metadata: Metadata = {
  title: "Review queue — bluntly admin",
};

type Tab = "reviews" | "answers" | "report" | "support";
const TABS: Tab[] = ["reviews", "answers", "report", "support"];

/**
 * The Review Queue's own route (frame 5017:3758).
 *
 * `tab` and `priority` come from the URL so the Overview's Queue Breakdown and
 * the header's "urgent" badge can link straight to a filtered queue, and so a
 * moderator can share the view they are looking at.
 */
export default async function ReviewQueuePage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; priority?: string }>;
}) {
  const params = await searchParams;
  const tab = (TABS as string[]).includes(params.tab ?? "")
    ? (params.tab as Tab)
    : "reviews";
  const priority =
    params.priority === "high"
      ? "High"
      : params.priority === "normal"
        ? "Normal"
        : params.priority === "low"
          ? "Low"
          : null;

  // The Answers tab reads the public Q&A endpoints. There is no `/admin` Q&A
  // route and this needs none: `GET /questions` already returns the asker,
  // the answer count and the trust of everyone involved, and the per-question
  // detail is fetched through the BFF only for the row a moderator opens.
  // `getQuestions` returns null when the API is unreachable — a failing Q&A
  // list must not blank the review queue, same defence as `getReports`. That
  // null is passed THROUGH rather than flattened to []: an outage and an empty
  // queue are different facts, and the tab says which one it is.
  const [{ pending, edited, fetchedAt }, reports, questions] = await Promise.all([
    getQueue(),
    getReports(),
    getQuestions(),
  ]);

  return (
    <ReviewQueueScreen
      pending={pending}
      edited={edited}
      reports={reports}
      questions={questions}
      initialTab={tab}
      initialPriority={priority}
      now={fetchedAt}
    />
  );
}
