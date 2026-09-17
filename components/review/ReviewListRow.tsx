import Image from "next/image";
import Link from "next/link";
import { ArrowFatUp, DotOutline, ImageSquare } from "@phosphor-icons/react/dist/ssr";

import { HonestyScore } from "@/components/ui/HonestyScore";
import type { ReviewCardData } from "@/lib/landing-data";
import { LAZY, type ImageHints } from "@/lib/list-image-hints";
import { splitHeadline } from "@/lib/reviews";

/**
 * A search result: Figma "ReviewPreviewCard" (7152:4714), as placed in "Mobile
 * Search Page for Buyers" (3481:1776). Read from the file on 2026-09-14.
 *
 * Search is a list, not the grid the landing rail uses: a grid is for browsing
 * by picture, a list is for scanning results you asked for.
 *
 * Phone values from the component: a 226px body and a 100px media square
 * pushed apart; a 24px avatar with the byline 8px after it and 3px down —
 * handle and score in 12px Poppins Light, the age in ExtraLight, separated by
 * 12px DotOutline glyphs in --base-gray-400; 12px down to the 14px title, the
 * product bold with its hyphen and the rest regular; 8px down to the stats — a
 * 16px ArrowFatUp in the success green and 12px Light counts, 3px apart. Cards
 * sit 20px under the rule above them and 21px over a 1px rule drawn at
 * --line-hairline-10.
 */

const Dot = () => (
  <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
);

export function ReviewListRow({
  review,
  imageHints = LAZY,
}: {
  review: ReviewCardData;
  /**
   * How this row's thumbnail loads — see lib/list-image-hints.ts. The rows on
   * screen at arrival load eagerly and the first one that actually HAS a photo
   * gets high fetch priority; the rest stay lazy. (This used to be `priority`
   * on row 0, which on production is usually a placeholder, so the real LCP
   * image further down loaded lazily.)
   */
  imageHints?: ImageHints;
}) {
  const headline = splitHeadline(review.title, review.product);

  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/reviews/${review.id}`}
        className="flex items-start justify-between gap-4 px-4 pb-[21px] pt-5 no-underline transition-colors hover:bg-[var(--line-hairline-10)] md:px-0 md:py-4 lg:gap-6 lg:py-5"
      >
        <div className="min-w-0 flex-1 max-md:max-w-[226px]">
          <div className="flex items-start gap-2">
            {review.avatarUrl ? (
              <Image
                src={review.avatarUrl}
                alt=""
                width={24}
                height={24}
                className="h-6 w-6 shrink-0 rounded-full object-cover"
              />
            ) : (
              <span
                aria-hidden="true"
                className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-semibold text-white"
                style={{ background: `hsl(${review.authorHue} 55% 55%)` }}
              >
                {review.author.slice(0, 1).toUpperCase()}
              </span>
            )}
            <p className="mt-[3px] flex min-w-0 items-center gap-1 text-[12px] leading-none text-[var(--text-primary)]">
              <span className="truncate font-light">{review.username ?? review.author}</span>
              {review.trustScore ? (
                <>
                  <Dot />
                  <HonestyScore
                    score={review.trustScore}
                    levelName={review.trustLevel}
                    stage={review.trustStage}
                  />
                </>
              ) : null}
              <Dot />
              <span className="shrink-0 font-extralight">{review.ageLabel}</span>
            </p>
          </div>

          <h2 className="mt-3 text-[14px] leading-[21px] text-[var(--text-primary)]">
            {headline.product ? (
              <>
                <span className="font-bold">{headline.product} - </span>
                {headline.rest}
              </>
            ) : (
              <span className="font-bold">{review.title}</span>
            )}
          </h2>

          <p className="mt-2 flex items-center gap-[3px] text-[12px] font-light leading-none text-[var(--text-primary)]">
            <ArrowFatUp
              size={16}
              weight="fill"
              aria-hidden="true"
              className="shrink-0 text-[var(--accent-success)]"
            />
            {review.upvotes}
            <span className="sr-only"> found this helpful</span>
            <Dot />
            {/* "1 comments" is the kind of thing that reads as machine output.
                upvotes/comments are pre-formatted strings ("14.8k"), so the
                singular only applies to a literal "1". */}
            {review.comments} {review.comments === "1" ? "comment" : "comments"}
          </p>
        </div>

        {/* 100px square, radius 16, on the component's #e1e1e1 media ground. */}
        <div className="relative h-[100px] w-[100px] shrink-0 overflow-hidden rounded-[16px] bg-[#e1e1e1] lg:h-[120px] lg:w-[120px]">
          {review.imageUrl ? (
            /* `sizes` is a WIDTH, but this box is cropped with object-cover:
               a 1200x630 source scaled to the box width has only ~62px of
               height for a 120px box and is upscaled back, which is visibly
               softer than the original. Declaring ~2x the box covers sources
               up to 2:1 without going back to full-size downloads. */
            <Image
              src={review.imageUrl}
              alt=""
              fill
              sizes="(min-width: 1024px) 240px, 200px"
              loading={imageHints.loading}
              fetchPriority={imageHints.fetchPriority}
              className="object-cover"
            />
          ) : (
            <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
              <ImageSquare size={24} weight="light" className="text-[var(--base-gray-400)]" />
            </div>
          )}
        </div>
      </Link>
    </li>
  );
}

export default ReviewListRow;
