import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowSquareOut, CaretCircleDown, DotOutline } from "@phosphor-icons/react/dist/ssr";

import { ClaimSellerForm } from "@/components/sellers/ClaimSellerForm";
import { SellerFigures } from "@/components/sellers/SellerFigures";
import { ClaimStatusLine, SellerAvatar } from "@/components/sellers/SellerIdentity";
import { SellerPageBar } from "@/components/sellers/SellerPageBar";
import { SellerRatingSummary } from "@/components/sellers/SellerRatingSummary";
import { SellerReviewSlide } from "@/components/sellers/SellerReviewSlide";
import { SellerReviewsSection } from "@/components/sellers/SellerReviewsSection";
import { PLATFORM_LABEL } from "@/components/sellers/seller-model";
import { ActionMenu } from "@/components/site/ActionMenu";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { getQuestions } from "@/lib/qa";
import { getMyStores, getSeller, getSellerReviews } from "@/lib/sellers";

export const metadata: Metadata = {
  title: "Seller — bluntly",
};

/** The API's ceiling on one page of seller reviews; the filter below runs over these. */
const REVIEWS_LOADED = 100;
const CAROUSEL = 6;

/**
 * A store's public profile (FR-4), built to "Seller Page - Review.png" and
 * "Seller Page - Questions.png" at 390: the orange phone bar, the store's mark,
 * claim line, name and counts, "Rate this seller" and "Ask a question", the
 * rating card, a two-row carousel of the newest reviews with "See all", then
 * the full list with its star filter, keyword search and Reviews / Questions
 * tabs.
 *
 * NOT RENDERED, because this product holds no data for them: the store banner,
 * logo and marketplace icons, "Responded to N negative reviews", Company
 * Details, Contact Information, and the "..." menu. Each would be invented store
 * content.
 *
 * REQUIRED, and added in the frame's visual language: the FR-4 figures under the
 * rating card, "Store dashboard" for the store's approved owner, "Visit store"
 * when a listing link exists, and the claim form for an unclaimed store.
 *
 * WEBSITE (`lg` and up): no frame; the phone column centred on a monitor is
 * what the owner rejected. The store's identity, rating card and figures stand
 * in a sticky column at the left, and the reviews, questions and claim form
 * read beside them.
 */
export default async function SellerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Parallel: the store, its reviews, its questions and the viewer are independent.
  const [seller, reviews, questions, me] = await Promise.all([
    getSeller(id),
    getSellerReviews(id, REVIEWS_LOADED),
    getQuestions(undefined, { sellerId: id, limit: 20 }),
    getUser().catch(() => null),
  ]);
  if (!seller) notFound();

  const user: HeaderUser = me ? { username: me.username, avatarUrl: me.avatar_url, role: me.role } : null;
  const canModerate = me?.role === "moderator" || me?.role === "admin";
  // The public store shape never says who claimed it, so ownership is asked of
  // the API — and only when it could be true, to spare everyone else a request.
  const ownsStore =
    me !== null && seller.claim_status === "claimed"
      ? (await getMyStores()).some((store) => store.id === seller.id)
      : false;
  const count = seller.review_count;
  const rateHref = `/sellers/rate?seller=${seller.id}`;
  const newest = (reviews ?? []).slice(0, CAROUSEL);
  // Figma "Frame 701" (4218:4684): 32px on white, a 1px outline, radius 20,
  // 12px sides and 12px Light type.
  const pill =
    "inline-flex h-8 items-center gap-1 rounded-[20px] border bg-[var(--surface-card)] px-3 text-[12px] font-light leading-none no-underline";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <div className="hidden md:block">
        <SiteHeader user={user} />
      </div>
      <SellerPageBar />

      <main className="mx-auto w-full max-w-[44rem] flex-1 px-4 pb-10 pt-5 md:py-10 lg:grid lg:max-w-[72rem] lg:grid-cols-[24rem_minmax(0,1fr)] lg:items-start lg:gap-12 lg:px-10">
        <div className="lg:sticky lg:top-[96px]">
          <div className="px-4 lg:px-0">
            {/* Figma 4218:2148: the 100px logo tile ("Rectangle 256"), the claim
              row 8px under it, the name 6px lower in 16px SemiBold, the counts
              8px lower in 12px Light around a 12px DotOutline, and the pills
              18px under those. */}
            <SellerAvatar name={seller.display_name} size={100} shape="tile" />
            <div className="mt-2">
              <ClaimStatusLine status={seller.claim_status} />
            </div>
            <h1 className="mt-1.5 text-[16px] font-semibold leading-none text-[var(--text-primary)]">
              {seller.display_name}
            </h1>
            <p className="mt-2 flex items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)]">
              {count} {count === 1 ? "review" : "reviews"}
              <DotOutline size={12} aria-hidden="true" className="text-[var(--base-gray-400)]" />
              {PLATFORM_LABEL[seller.platform]}
            </p>

            <div className="mt-[18px] flex flex-wrap gap-2">
              <Link
                href={rateHref}
                className={`${pill} border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[color-mix(in_srgb,var(--accent-primary)_8%,transparent)]`}
              >
                Rate this seller
              </Link>
              <a
                href="#all-reviews"
                className={`${pill} border-[var(--text-primary)] text-[var(--text-primary)] hover:border-[var(--accent-primary)]`}
              >
                Ask a question
              </a>
              {ownsStore ? (
                <Link
                  href={`/sellers/${seller.id}/dashboard`}
                  className={`${pill} border-[var(--accent-trust)] text-[var(--accent-trust)] hover:bg-[color-mix(in_srgb,var(--accent-trust)_8%,transparent)]`}
                >
                  Store dashboard
                </Link>
              ) : null}
              {seller.store_url ? (
                <a
                  href={seller.store_url}
                  target="_blank"
                  rel="nofollow noopener noreferrer"
                  className={`${pill} border-[var(--text-primary)] text-[var(--text-primary)] hover:border-[var(--accent-primary)]`}
                >
                  Visit store <ArrowSquareOut size={14} aria-hidden="true" />
                </a>
              ) : null}
            </div>
          </div>

          <div className="mt-4">
            <SellerRatingSummary summary={seller.summary} />
          </div>
          <div className="mt-5">
            <SellerFigures summary={seller.summary} />
          </div>
        </div>

        <div className="min-w-0">
          <hr className="mt-6 border-0 border-t border-[var(--line-hairline-30)] lg:hidden" />

          <h2 className="mt-5 text-[16px] font-semibold leading-none text-[var(--text-primary)] lg:mt-0">
            Seller Reviews
          </h2>
          {newest.length > 0 ? (
            <>
              {/* Two rows that scroll together, filled top then bottom, as drawn. */}
              <ul
                aria-label="Newest reviews"
                // `scroll-px-4` matches the padding: without it `snap-start` aligns
                // the first card to the scroller's edge and cuts off its border.
                className={`-mx-4 mt-6 grid snap-x scroll-px-4 auto-cols-[264px] grid-flow-col gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] ${
                  newest.length > 1 ? "grid-rows-2" : "grid-rows-1"
                }`}
              >
                {newest.map((review) => (
                  <SellerReviewSlide key={review.id} review={review} />
                ))}
              </ul>
              <a
                href="#all-reviews"
                className="mt-5 flex h-12 items-center justify-center gap-1 rounded-[var(--radius-pill)] bg-[#dfdfdf] text-[14px] leading-none text-[var(--text-primary)] no-underline hover:bg-[var(--base-gray-200)]"
              >
                See all {count} {count === 1 ? "review" : "reviews"}
                <CaretCircleDown size={20} aria-hidden="true" />
              </a>
            </>
          ) : (
            <p className="mt-3 text-[12px] font-light text-[var(--text-secondary)]">
              {reviews === null ? "Reviews could not be loaded right now." : "Nobody has rated this seller yet."}
            </p>
          )}

          <hr className="mt-5 border-0 border-t border-[var(--line-hairline-30)]" />

          <div className="mt-6">
            <SellerReviewsSection
              sellerId={seller.id}
              summary={seller.summary}
              reviews={reviews}
              questions={questions}
              claimed={seller.claim_status === "claimed"}
              signedIn={Boolean(me)}
              canModerate={canModerate}
            />
          </div>

          {seller.claim_status !== "claimed" ? (
            <section className="mt-12 border-t border-[var(--line-hairline-10)] pt-8">
              <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">Do you run this store?</h2>
              <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
                Claim it to be recognised as the seller. A moderator checks every claim against the public listing
                before anything on this page changes.
              </p>
              <ClaimSellerForm sellerId={seller.id} signedIn={Boolean(me)} />
            </section>
          ) : null}
        </div>
      </main>
      <ActionMenu sellerId={seller.id} />
      <SiteFooter />
    </div>
  );
}
