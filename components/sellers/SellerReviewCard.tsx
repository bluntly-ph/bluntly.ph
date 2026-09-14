import Image from "next/image";

import { TrustBadge } from "@/components/ui/TrustBadge";
import type { SellerReview } from "@/lib/sellers";

import { RemoveSellerReviewButton } from "./RemoveSellerReviewButton";
import { StarRow } from "./SellerIdentity";

/**
 * One buyer's rating of a store, as "Seller Page - Review.png" draws it: the
 * reviewer and their trust score, the stars, a bold title, and the prose.
 *
 * NOT RENDERED, because none of it exists for seller reviews: the vote counts,
 * comment counts and share control on the frame's cards, and the seller's
 * public reply. Drawing them would mean drawing numbers nobody produced.
 *
 * Added under the prose, as REQUIRED FUNCTIONALITY: the four FR-4 answers this
 * buyer gave. They are what makes a seller review different from a product
 * review, and the frame's cards have no other place for them.
 */

const DATE = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeZone: "Asia/Manila" });

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
    <li className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
        <span className="font-medium text-[var(--text-primary)]">
          {reviewer?.username ?? reviewer?.display_name ?? "Former member"}
        </span>
        {reviewer ? (
          <TrustBadge
            levelName={reviewer.trust_level_name}
            stage={reviewer.trust_stage}
            score={reviewer.reputation_score}
            plain
            compact
          />
        ) : null}
        <span className="text-[var(--text-muted)]">
          <time dateTime={review.created_at}>{DATE.format(new Date(review.created_at))}</time>
        </span>
      </div>

      <StarRow value={review.overall_rating} size={20} className="mt-3" />

      {review.title ? (
        <h3 className="mt-2 text-[16px] font-bold text-[var(--text-primary)]">{review.title}</h3>
      ) : null}
      {review.comment ? (
        <p className="mt-1 whitespace-pre-line text-[14px] leading-[20px] text-[var(--text-primary)]">
          {review.comment}
        </p>
      ) : null}

      <ul aria-label="This buyer's answers" className="mt-3 flex flex-wrap gap-2 text-[12px]">
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
