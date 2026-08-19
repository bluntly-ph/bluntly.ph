import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CommentThread } from "@/components/review/CommentThread";
import { PricePanel } from "@/components/product/PricePanel";
import { ReviewDetail } from "@/components/review/ReviewDetail";
import { SiteFooter } from "@/components/site/SiteFooter";
import { getComments } from "@/lib/comments";
import { getUser } from "@/lib/dal";
import { getPricePanel } from "@/lib/products";
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

  // Necessarily sequential: the panel is keyed by product id, which only the
  // review response carries. It is one small cached read (revalidate 60) and
  // returns null on failure, so a price-service wobble costs the panel rather
  // than the page.
  const pricePanel = data.product ? await getPricePanel(data.product.id) : null;

  let canVote = false;
  let isOwnReview = false;
  let viewerId: string | null = null;
  if (me) {
    viewerId = me.id;
    isOwnReview = me.id === data.author?.id;
    // You may vote on any published review except your own.
    canVote = !isOwnReview;
  }

  return (
    // No SiteHeader here on purpose: the frame gives the review its own orange
    // nav bar carrying back / shop / overflow / search / profile, so the global
    // header would stack a second, redundant one above it.
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <main className="flex-1">
        <ReviewDetail data={data} canVote={canVote} isOwnReview={isOwnReview} />
        <div className="mx-auto w-full max-w-[44rem] px-4 pb-10 lg:px-6">
          {/* FR-2 price panel. Rendered on the review because this is the
              product surface today — there is no standalone product page. It
              sits above the comments so price context arrives while the
              reader is still weighing the verdict, not after the discussion. */}
          {data.product ? <PricePanel panel={pricePanel} /> : null}
          <CommentThread reviewId={id} initial={comments} viewerId={viewerId} />
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
