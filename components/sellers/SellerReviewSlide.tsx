import { TrustBadge } from "@/components/ui/TrustBadge";
import type { SellerReview } from "@/lib/sellers";

import { ReviewerInitial, StarRow } from "./SellerIdentity";
import { shortAge } from "./seller-model";

/**
 * One card in the "Seller Reviews" carousel, measured from "Seller Page -
 * Review.png": 264px wide and 242px tall at radius 16, #f6f6f6 with a #dedada
 * border and a 20px inset; a 36px reviewer disc, the name and trust score at
 * 13px with the age under it; 20px stars; the prose at 13/20px, four lines,
 * then "See more", which jumps to the same review in the full list below.
 *
 * NOT RENDERED: the frame's vote counts, comment count, share and "..." on each
 * card. Seller reviews have no votes, comments or per-card actions here.
 */
export function SellerReviewSlide({ review }: { review: SellerReview }) {
  const reviewer = review.reviewer;
  const name = reviewer?.username ?? reviewer?.display_name ?? "Former member";
  const prose = review.comment ?? review.title ?? "";

  return (
    <li className="flex min-h-[242px] w-[264px] snap-start flex-col rounded-[16px] border border-[#dedada] bg-[#f6f6f6] p-5">
      <div className="flex items-center gap-[9px]">
        <ReviewerInitial name={name} />
        <div className="min-w-0 font-[family-name:var(--font-system)]">
          <p className="flex items-center gap-1 text-[13px] text-[var(--text-primary)]">
            <span className="truncate">{name}</span>
            {reviewer ? (
              <>
                <span aria-hidden="true" className="text-[var(--text-muted)]">
                  •
                </span>
                <TrustBadge
                  levelName={reviewer.trust_level_name}
                  stage={reviewer.trust_stage}
                  score={reviewer.reputation_score}
                  plain
                  compact
                />
              </>
            ) : null}
          </p>
          <p className="text-[11px] text-[var(--text-secondary)]">
            <time dateTime={review.created_at}>{shortAge(review.created_at)}</time>
          </p>
        </div>
      </div>

      <StarRow value={review.overall_rating} size={20} className="mt-[14px]" />

      <p className="mt-[14px] line-clamp-4 font-[family-name:var(--font-system)] text-[13px] leading-5 text-[var(--text-primary)]">
        {prose}
      </p>
      <a
        href={`#seller-review-${review.id}`}
        className="mt-auto pt-1 font-[family-name:var(--font-system)] text-[13px] text-[var(--accent-trust)]"
      >
        See more<span className="sr-only"> of {name}&rsquo;s review</span>
      </a>
    </li>
  );
}

export default SellerReviewSlide;
