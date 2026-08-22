import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CommentThread } from "@/components/review/CommentThread";
import { PricePanel } from "@/components/product/PricePanel";
import { ReviewAside } from "@/components/review/ReviewAside";
import { ReviewDetail } from "@/components/review/ReviewDetail";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getComments } from "@/lib/comments";
import { getUser } from "@/lib/dal";
import { getPricePanel } from "@/lib/products";
import { getReviewFull, searchReviews } from "@/lib/reviews";
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
  const [pricePanel, relatedRaw] = await Promise.all([
    data.product ? getPricePanel(data.product.id) : Promise.resolve(null),
    // Related reviews for the desktop sidebar, from the public feed filtered by
    // this product's category — no new endpoint, and nothing that is not already
    // public. Over-fetched by one so removing this review still leaves four.
    data.product?.category
      ? searchReviews({ category: data.product.category, sort: "wilson", limit: 5 })
      : Promise.resolve(null),
  ]);
  const related = (relatedRaw ?? []).filter((r) => r.id !== id).slice(0, 4);

  const headerUser: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;

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
      {/* Tablet and up get the site's own header; the review's orange bar is
          phone chrome and hides itself at the same breakpoint. The sidebar
          waits for `lg` — 768px has room for navigation, not for a column. */}
      <div className="hidden md:block">
        <SiteHeader user={headerUser} />
      </div>

      <main className="flex-1">
        <div className="mx-auto w-full lg:max-w-[76rem] lg:px-10 lg:py-10">
          <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:gap-12">
            <div className="min-w-0">
              <ReviewDetail data={data} canVote={canVote} isOwnReview={isOwnReview} />

              <div className="mx-auto w-full max-w-[44rem] px-4 pb-10 lg:mx-0 lg:max-w-[42rem] lg:px-0">
                {/* FR-2 price panel. Rendered on the review because this is the
                    product surface today — there is no standalone product page.
                    It sits above the comments so price context arrives while the
                    reader is still weighing the verdict, not after the
                    discussion. On desktop it moves into the sidebar, where
                    supporting context belongs. */}
                {data.product ? (
                  <div className="lg:hidden">
                    <PricePanel panel={pricePanel} />
                  </div>
                ) : null}
                <CommentThread reviewId={id} initial={comments} viewerId={viewerId} />
              </div>
            </div>

            {/* Sticky because the reading column is long — a 2,273px review
                would otherwise strand the product, its price and the Buy action
                at the very top, which is where they are least useful. */}
            <aside className="hidden lg:block lg:sticky lg:top-28">
              <ReviewAside data={data} panel={pricePanel} related={related} />
            </aside>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
