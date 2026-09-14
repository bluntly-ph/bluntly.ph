import Image from "next/image";
import { DotOutline } from "@phosphor-icons/react/dist/ssr";

import { HonestyScore } from "@/components/ui/HonestyScore";
import type { SellerReview } from "@/lib/sellers";

import { RemoveSellerReviewButton } from "./RemoveSellerReviewButton";
import { ReviewerInitial, StarRow } from "./SellerIdentity";
import { shortAge } from "./seller-model";

/**
 * One buyer's rating of a store in the full "All reviews" list: Figma "Group
 * 696" (4295:1153), read 2026-09-14. A 36px reviewer disc with the byline 8px
 * after it — name, 16px DotOutline, Honesty Score, DotOutline, trust level, all
 * 12px Light — and the age in 12px ExtraLight beneath; 12px down to 20px stars;
 * 12px down to the title in 14px Bold on its natural line, then 4px to the prose
 * in 12px Light at 1.5. No card chrome — the frame's list items sit on the page.
 *
 * NOT RENDERED, because none of it exists for seller reviews: vote counts,
 * Reply, Share, the "..." menu, and the store's public reply.
 *
 * Added under the prose, as REQUIRED FUNCTIONALITY: the four FR-4 answers this
 * buyer gave. They are what makes a seller review different from a product
 * review, and the frame's items have no other place for them.
 */

function chip(positive: boolean): string {
  return positive
    ? "bg-[color-mix(in_srgb,var(--accent-success)_12%,transparent)] text-[var(--text-primary)]"
    : "bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] text-[var(--text-primary)]";
}

export function SellerReviewCard({
  review,
  canModerate = false,
}: {
  review: SellerReview;
  /** Draws the moderator's remove control. The API enforces the role. */
  canModerate?: boolean;
}) {
  const reviewer = review.reviewer;
  const name = reviewer?.username ?? reviewer?.display_name ?? "Former member";
  const answers: { label: string; positive: boolean }[] = [
    { label: review.accuracy ? "Matched the listing" : "Not as listed", positive: review.accuracy },
    {
      label: review.order_completeness ? "Exact order" : "Missing item",
      positive: review.order_completeness,
    },
    {
      label: review.would_recommend ? "Recommends" : "Doesn’t recommend",
      positive: review.would_recommend,
    },
    { label: `Service ${review.customer_service}/5`, positive: review.customer_service >= 3 },
    { label: `Packaging ${review.packaging_quality}/5`, positive: review.packaging_quality >= 3 },
  ];

  return (
    <li id={`seller-review-${review.id}`} className="scroll-mt-24">
      <div className="flex items-center gap-2">
        <ReviewerInitial name={name} />
        <div className="min-w-0 text-[var(--text-primary)]">
          <p className="flex flex-wrap items-center text-[12px] font-light leading-4">
            <span className="truncate">{name}</span>
            {reviewer ? (
              <>
                <DotOutline size={16} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                <HonestyScore
                  score={reviewer.reputation_score}
                  levelName={reviewer.trust_level_name}
                  stage={reviewer.trust_stage}
                />
                {reviewer.trust_level_name ? (
                  <>
                    <DotOutline size={16} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                    <span aria-hidden="true">{reviewer.trust_level_name}</span>
                  </>
                ) : null}
              </>
            ) : null}
          </p>
          <p className="text-[12px] font-extralight leading-[18px]">
            <time dateTime={review.created_at}>{shortAge(review.created_at)}</time>
          </p>
        </div>
      </div>

      <StarRow value={review.overall_rating} size={20} gap={0} className="mt-3" />

      {review.title ? (
        <h3 className="mt-3 text-[14px] font-bold leading-[21px] text-[var(--text-primary)]">{review.title}</h3>
      ) : null}
      {review.comment ? (
        <p className={`${review.title ? "mt-1" : "mt-3"} whitespace-pre-line text-[12px] font-light leading-[18px] text-[var(--text-primary)]`}>
          {review.comment}
        </p>
      ) : null}

      <ul aria-label="This buyer's answers" className="mt-3 flex flex-wrap gap-2 text-[12px] font-light">
        {answers.map((answer) => (
          <li
            key={answer.label}
            className={`rounded-[var(--radius-pill)] px-2.5 py-1 ${chip(answer.positive)}`}
          >
            {answer.label}
          </li>
        ))}
      </ul>

      {review.photo_urls.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {review.photo_urls.map((url, i) => (
            <li
              key={url}
              className="relative h-20 w-20 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--base-gray-200)]"
            >
              <Image
                src={url}
                alt={`Photo ${i + 1} from this review`}
                fill
                sizes="80px"
                className="object-cover"
              />
            </li>
          ))}
        </ul>
      ) : null}

      {canModerate ? <RemoveSellerReviewButton reviewId={review.id} /> : null}
    </li>
  );
}

export default SellerReviewCard;
