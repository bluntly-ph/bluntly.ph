import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CommentThread } from "@/components/review/CommentThread";
import { ReviewDetail } from "@/components/review/ReviewDetail";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getComments } from "@/lib/comments";
import { getUser } from "@/lib/dal";
import { getReviewFull } from "@/lib/reviews";
import { getSessionToken } from "@/lib/session";

export const metadata: Metadata = {
  title: "Review — bluntly",
};

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // The cookie read is local, so the token is free before the network work.
  const token = await getSessionToken();
  // One parallel round instead of three sequential ones. These calls are
  // independent, and awaiting them in series cost a full backend round trip
  // each — the page measured 2.9s against a database whose queries run in
  // single-digit milliseconds. `getUser` keeps its own catch so a backend
  // wobble degrades to "signed out" rather than rejecting the whole batch.
  const [data, me, comments] = await Promise.all([
    // Token passed so the review arrives with the viewer's own vote (BUG-013).
    // For signed-out readers this is undefined, which keeps the cached path.
    getReviewFull(id, token),
    getUser().catch(() => null),
    // Sent with the viewer's token so the thread comes back carrying their own
    // votes; signed-out readers get the same thread with `my_vote` null.
    getComments(id, token),
  ]);
  if (!data) notFound();

  let user: HeaderUser = null;
  let canVote = false;
  let isOwnReview = false;
  let viewerId: string | null = null;
  if (me) {
    user = { username: me.username, avatarUrl: me.avatar_url };
    viewerId = me.id;
    isOwnReview = me.id === data.author?.id;
    // You may vote on any published review except your own.
    canVote = !isOwnReview;
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="flex-1">
        <ReviewDetail data={data} canVote={canVote} isOwnReview={isOwnReview} />
        <div className="mx-auto w-full max-w-[44rem] px-6 pb-10">
          <CommentThread reviewId={id} initial={comments} viewerId={viewerId} />
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
