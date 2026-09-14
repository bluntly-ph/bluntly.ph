import { DotOutline } from "@phosphor-icons/react/dist/ssr";

import { HonestyScore } from "@/components/ui/HonestyScore";
import type { SellerReview } from "@/lib/sellers";

import { ReviewerInitial, StarRow } from "./SellerIdentity";
import { shortAge } from "./seller-model";

/**
 * One card in the "Seller Reviews" carousel: Figma "Group 673" (4264:5138),
 * read 2026-09-14.
 *
 * 264x242 at radius 16, white at 30% over the page with a #aea2a2 outline at
 * the same 30% (#f6f6f6 on #dedada), 20px in. A 36px reviewer disc with the
 * byline 8px after it — the name in 12px Light, a 16px DotOutline, the Honesty
 * Score — and the age in 12px ExtraLight beneath; 12px down to 20px stars; 8px
 * down to the prose in 12px Light on an 18px line, then "See more" in 12px
 * Regular trust blue, which jumps to the same review in the full list below.
 *
 * NOT RENDERED: the frame's vote bar, comment count, share and "..." on each
 * card. Seller reviews have no votes, comments or per-card actions here.
 */
export function SellerReviewSlide({ review }: { review: SellerReview }) {
  const reviewer = review.reviewer;
  const name = reviewer?.username ?? reviewer?.display_name ?? "Former member";
  const prose = review.comment ?? review.title ?? "";

  return (
    <li className="flex min-h-[242px] w-[264px] snap-start flex-col rounded-[16px] border border-[#dedada] bg-[#f6f6f6] p-5 text-[var(--text-primary)]">
      <div className="flex items-center gap-2">
        <ReviewerInitial name={name} />
        <div className="min-w-0">
          <p className="flex items-center text-[12px] font-light leading-4">
            <span className="truncate">{name}</span>
            {reviewer ? (
              <>
                <DotOutline size={16} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                <HonestyScore
                  score={reviewer.reputation_score}
                  levelName={reviewer.trust_level_name}
                  stage={reviewer.trust_stage}
                />
              </>
            ) : null}
          </p>
          <p className="text-[12px] font-extralight leading-[18px]">
            <time dateTime={review.created_at}>{shortAge(review.created_at)}</time>
          </p>
        </div>
      </div>

      <StarRow value={review.overall_rating} size={20} gap={0} className="mt-3" />

      <p className="mt-2 line-clamp-4 text-[12px] font-light leading-[18px]">{prose}</p>
      <a
        href={`#seller-review-${review.id}`}
        className="mt-auto pt-1 text-[12px] leading-[18px] text-[var(--accent-trust)]"
      >
        See more<span className="sr-only"> of {name}&rsquo;s review</span>
      </a>
    </li>
  );
}

export default SellerReviewSlide;
