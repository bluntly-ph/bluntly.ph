import Image from "next/image";
import Link from "next/link";
import { ArrowFatUp, ImageSquare } from "@phosphor-icons/react/dist/ssr";

import { TrustBadge } from "@/components/ui/TrustBadge";
import type { ReviewCardData } from "@/lib/landing-data";
import { splitHeadline } from "@/lib/reviews";

/**
 * A search result, as "Mobile Search Page for Buyers.png" draws it.
 *
 * Search is a list, not the grid the landing rail uses: an author line, the
 * split title, the stats, and a 100px square thumbnail pinned right, with a
 * full-bleed rule between rows. A grid is for browsing by picture, a list is
 * for scanning results you asked for, and search is the second thing.
 *
 * Phone values measured from the frame (390 wide): rows on a 144px pitch with
 * 20px above and 24px below the content, a 2px --base-gray-150 rule, a 24px
 * avatar, the author at 13px, a 16/22px title — the product bold with its
 * hyphen, the rest regular — a green up-arrow with the helpful count and the
 * comment count at 13px, and a 100px thumbnail at radius 16.
 */
export function ReviewListRow({
  review,
  priority = false,
}: {
  review: ReviewCardData;
  /**
   * Set on the first row only. Its thumbnail is above the fold and is the
   * element LCP is measured on, so lazy-loading it deprioritises the one image
   * the score depends on — Lighthouse measured /search LCP between 3.0s and
   * 9.4s across three runs while FCP held steady at 1.0s, which is the shape of
   * a late-arriving hero image rather than a slow page.
   *
   * Every other row stays lazy: they are below the fold and eager-loading them
   * would trade one metric for page weight.
   */
  priority?: boolean;
}) {
  const headline = splitHeadline(review.title, review.product);

  return (
    <li className="border-b-2 border-[var(--base-gray-150)] md:border-b md:border-[var(--line-hairline-10)]">
      <Link
        href={`/reviews/${review.id}`}
        className="flex items-start gap-3 px-4 pb-6 pt-5 transition-colors hover:bg-[var(--line-hairline-10)] md:gap-4 md:px-0 md:py-4 lg:gap-6 lg:py-5"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
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
            <span className="truncate text-[13px] text-[var(--text-primary)]">
              {review.username ?? review.author}
            </span>
            <TrustBadge
              levelName={review.trustLevel}
              stage={review.trustStage}
              score={review.trustScore}
              plain
              compact
            />
            <span className="text-[13px] text-[var(--text-muted)]">· {review.ageLabel}</span>
          </div>

          <h2 className="mt-3 text-[16px] leading-[22px] text-[var(--text-primary)]">
            {headline.product ? (
              <>
                <span className="font-bold">{headline.product} -</span> {headline.rest}
              </>
            ) : (
              <span className="font-bold">{review.title}</span>
            )}
          </h2>

          <p className="mt-2.5 flex items-center text-[13px] text-[var(--text-primary)]">
            <ArrowFatUp
              size={14}
              weight="fill"
              aria-hidden="true"
              className="mr-1.5 shrink-0 text-[var(--accent-success)]"
            />
            {review.upvotes}
            <span className="sr-only"> found this helpful</span>
            <span aria-hidden="true" className="mx-1.5 text-[var(--text-muted)]">
              •
            </span>
            {/* "1 comments" is the kind of thing that reads as machine output.
                upvotes/comments are pre-formatted strings ("14.8k"), so the
                singular only applies to a literal "1". */}
            {review.comments} {review.comments === "1" ? "comment" : "comments"}
          </p>
        </div>

        {/* 100px square, radius 16, pinned right. */}
        <div className="relative h-[100px] w-[100px] shrink-0 overflow-hidden rounded-[16px] bg-[var(--surface-card)] lg:h-[120px] lg:w-[120px]">
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
              priority={priority}
              className="object-cover"
            />
          ) : (
            <div
              aria-hidden="true"
              className="absolute inset-0 grid place-items-center"
              style={{
                background: `linear-gradient(150deg, hsl(${review.imageHue} 42% 74%), hsl(${review.imageHue + 24} 38% 55%))`,
              }}
            >
              <ImageSquare size={24} weight="light" className="text-white/55" />
            </div>
          )}
        </div>
      </Link>
    </li>
  );
}

export default ReviewListRow;
