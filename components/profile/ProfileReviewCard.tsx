import Image from "next/image";
import Link from "next/link";
import { ArrowFatUp, ChatsCircle, DotOutline } from "@phosphor-icons/react/dist/ssr";

import { HonestyScore } from "@/components/ui/HonestyScore";
import type { ReviewCardData } from "@/lib/landing-data";
import { LAZY, type ImageHints } from "@/lib/list-image-hints";
import { splitHeadline } from "@/lib/reviews";

/**
 * A review in a profile's feed: Figma "Profile Page - Reviews" (5446:4328),
 * read 2026-09-15. 358px wide, 20px under the rule above it: a 36px avatar
 * 8px before the handle and Honesty Score in 12px Light (a 16px DotOutline
 * between) with the age under them in 12px ExtraLight; 12px lower the photo,
 * square at radius 16; 12px lower the headline in 14px, the product Bold and
 * the rest Regular; 4px lower a 32px row of outline pills — 1px at 30% ink,
 * radius 20, 12px in, a glyph 4px before 12px counts. A full-bleed hairline
 * 20px under the row.
 *
 * INTENTIONAL PRODUCT DIFFERENCES: the "170.3k" views pill (no view count is
 * served to the feed), the overflow menu and the share circle (both live on
 * the review page, where there is a review to act on) are not drawn; a review
 * without a photo drops the square rather than showing an empty 358px block.
 *
 * From `md` the feed is a two-column grid (beside the profile card from `lg`), so each
 * review becomes its own white card instead of a hairline-separated row.
 */
export function ProfileReviewCard({ review, imageHints = LAZY }: { review: ReviewCardData; imageHints?: ImageHints }) {
  const headline = splitHeadline(review.title, review.product);
  const pill =
    "inline-flex h-8 items-center gap-1 rounded-[20px] border border-[rgba(32,32,32,0.3)] px-[11px] text-[12px] leading-none text-[var(--text-primary)]";

  return (
    <li className="border-b border-[var(--line-hairline-10)] px-4 py-5 md:rounded-[16px] md:border-b-0 md:bg-[var(--surface-card)] md:p-4 md:shadow-[var(--shadow-card)]">
      <article className="mx-auto w-full max-w-[358px] md:max-w-none">
        <Link href={`/reviews/${review.id}`} className="block text-[var(--text-primary)] no-underline">
          <div className="flex h-9 items-center gap-2">
            {review.avatarUrl ? (
              <Image src={review.avatarUrl} alt="" width={36} height={36} className="h-9 w-9 shrink-0 rounded-full object-cover" />
            ) : (
              <span
                aria-hidden="true"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-[14px] font-semibold text-white"
                style={{ background: `hsl(${review.authorHue} 55% 55%)` }}
              >
                {review.author.slice(0, 1).toUpperCase()}
              </span>
            )}
            <div className="min-w-0">
              <p className="flex items-center text-[12px] font-light leading-none">
                <span className="truncate">{review.username ?? review.author}</span>
                {review.trustScore ? (
                  <>
                    <DotOutline size={16} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                    <HonestyScore score={review.trustScore} levelName={review.trustLevel} stage={review.trustStage} />
                  </>
                ) : null}
              </p>
              <p className="text-[12px] font-extralight leading-[18px]">{review.ageLabel}</p>
            </div>
          </div>

          {review.imageUrl ? (
            <div className="relative mt-3 aspect-square w-full overflow-hidden rounded-[16px] bg-[#e1e1e1]">
              <Image
                src={review.imageUrl}
                alt=""
                fill
                sizes="(min-width: 768px) 380px, 358px"
                loading={imageHints.loading}
                fetchPriority={imageHints.fetchPriority}
                className="object-cover"
              />
            </div>
          ) : null}

          <h2 className="mt-3 text-[14px] leading-[21px]">
            {headline.product ? (
              <>
                <span className="font-bold">{headline.product} - </span>
                {headline.rest}
              </>
            ) : (
              <span className="font-bold">{review.title}</span>
            )}
          </h2>
        </Link>

        <div className="mt-1 flex h-8 items-center justify-end gap-2">
          <span className={`${pill} font-light`}>
            <ArrowFatUp size={20} weight="fill" aria-hidden="true" className="text-[var(--accent-success)]" />
            {review.upvotes}
            <span className="sr-only"> found this helpful</span>
          </span>
          <span className={pill}>
            <ChatsCircle size={16} aria-hidden="true" />
            {review.comments}
            <span className="sr-only">{review.comments === "1" ? " comment" : " comments"}</span>
          </span>
        </div>
      </article>
    </li>
  );
}

export default ProfileReviewCard;
