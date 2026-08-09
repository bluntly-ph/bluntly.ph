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
  const data = await getReviewFull(id);
  if (!data) notFound();

  let user: HeaderUser = null;
  let canVote = false;
  let isOwnReview = false;
  let viewerId: string | null = null;
  try {
    const me = await getUser();
    if (me) {
      user = { username: me.username, avatarUrl: me.avatar_url };
      viewerId = me.id;
      isOwnReview = me.id === data.author?.id;
      // You may vote on any published review except your own.
      canVote = !isOwnReview;
    }
  } catch {
    user = null;
  }

  // Sent with the viewer's token so the thread comes back carrying their own
  // votes; signed-out readers get the same thread with `my_vote` null.
  const comments = await getComments(id, await getSessionToken());

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
