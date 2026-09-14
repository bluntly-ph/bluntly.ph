import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowSquareOut, Info } from "@phosphor-icons/react/dist/ssr";

import { ClaimSellerForm } from "@/components/sellers/ClaimSellerForm";
import { ClaimStatusLine, SellerAvatar } from "@/components/sellers/SellerIdentity";
import { SellerRatingSummary } from "@/components/sellers/SellerRatingSummary";
import { SellerReviewCard } from "@/components/sellers/SellerReviewCard";
import { PLATFORM_LABEL } from "@/components/sellers/seller-model";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { Unavailable } from "@/components/site/Unavailable";
import { getUser } from "@/lib/dal";
import { getSeller, getSellerReviews } from "@/lib/sellers";

export const metadata: Metadata = {
  title: "Seller — bluntly",
};

/**
 * A store's public profile (FR-4), built to "Seller Page - Review.png".
 *
 * NOT RENDERED, because this product holds no data for them: the store banner
 * and logo, "Responded to N negative reviews", Company Details and Contact
 * Information, "Ask a question" and the seller Questions tab (questions are
 * product-scoped and not linked to stores), and the review filters. Each is a
 * block of invented store content if drawn now.
 */
export default async function SellerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Parallel: the store, its reviews and the viewer are independent.
  const [seller, reviews, me] = await Promise.all([
    getSeller(id),
    getSellerReviews(id),
    getUser().catch(() => null),
  ]);
  if (!seller) notFound();

  const user: HeaderUser = me ? { username: me.username, avatarUrl: me.avatar_url } : null;
  const canModerate = me?.role === "moderator" || me?.role === "admin";
  const count = seller.review_count;
  const rateHref = `/sellers/rate?seller=${seller.id}`;
  const pill =
    "inline-flex h-9 items-center gap-1.5 rounded-[var(--radius-pill)] border px-4 text-[14px] no-underline";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[44rem] flex-1 px-6 py-8 lg:py-10">
        <div className="flex items-center gap-4 sm:gap-5">
          <SellerAvatar name={seller.display_name} size={88} />
          <div className="min-w-0">
            <ClaimStatusLine status={seller.claim_status} />
            <h1 className="mt-1 text-[22px] font-bold leading-snug text-[var(--text-primary)]">
              {seller.display_name}
            </h1>
            <p className="mt-0.5 text-[14px] text-[var(--text-secondary)]">
              {count} {count === 1 ? "review" : "reviews"} · {PLATFORM_LABEL[seller.platform]}
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href={rateHref}
            className={`${pill} border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[color-mix(in_srgb,var(--accent-primary)_8%,transparent)]`}
          >
            Rate this seller
          </Link>
          {seller.store_url ? (
            <a
              href={seller.store_url}
              target="_blank"
              rel="nofollow noopener noreferrer"
              className={`${pill} border-[var(--base-gray-600)] text-[var(--text-primary)] hover:border-[var(--accent-primary)]`}
            >
              Visit store <ArrowSquareOut size={14} aria-hidden="true" />
            </a>
          ) : null}
        </div>

        <div className="mt-6">
          <SellerRatingSummary summary={seller.summary} />
        </div>

        <p className="mt-6 flex gap-2 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-4 py-3 text-[13px] text-[var(--text-primary)]">
          <Info size={18} aria-hidden="true" className="shrink-0 text-[var(--accent-trust)]" />
          Reviews are the opinions of individual buyers and not of Bluntly.ph.
        </p>

        <h2 className="mt-10 text-[18px] font-semibold text-[var(--text-primary)]">Seller Reviews</h2>
        {reviews === null ? (
          <Unavailable what="seller reviews" />
        ) : reviews.length === 0 ? (
          <p className="mt-3 text-[14px] text-[var(--text-secondary)]">
            Nobody has rated this seller yet.{" "}
            <Link href={rateHref} className="text-[var(--accent-primary)]">
              Be the first
            </Link>
            .
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-4">
            {reviews.map((review) => (
              <SellerReviewCard key={review.id} review={review} canModerate={canModerate} />
            ))}
          </ul>
        )}

        {seller.claim_status !== "claimed" ? (
          <section className="mt-12 border-t border-[var(--line-hairline-10)] pt-8">
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
              Do you run this store?
            </h2>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
              Claim it to be recognised as the seller. A moderator checks every claim against the
              public listing before anything on this page changes.
            </p>
            <ClaimSellerForm sellerId={seller.id} signedIn={Boolean(me)} />
          </section>
        ) : null}
      </main>
      <SiteFooter />
    </div>
  );
}
