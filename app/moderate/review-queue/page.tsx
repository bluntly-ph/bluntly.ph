import type { Metadata } from "next";

import { ReviewQueueScreen } from "@/components/admin/ReviewQueueScreen";
import { getQueue, getReports } from "@/lib/moderation";

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

  const [{ pending, edited }, reports] = await Promise.all([getQueue(), getReports()]);

  return (
    <ReviewQueueScreen
      pending={pending}
      edited={edited}
      reports={reports}
      initialTab={tab}
      initialPriority={priority}
    />
  );
}
