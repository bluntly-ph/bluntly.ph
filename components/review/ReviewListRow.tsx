import Link from "next/link";
import { ImageSquare } from "@phosphor-icons/react/dist/ssr";

import { TrustBadge } from "@/components/ui/TrustBadge";
import type { ReviewCardData } from "@/lib/landing-data";
import { splitHeadline } from "@/lib/reviews";

/**
 * A search result, as the Page 1 frame draws it.
 *
 * Search is a list, not the grid the landing rail uses: an author line, the
 * split title, the stats, and a 100px square thumbnail pinned right, with a
 * full-bleed hairline between rows. The distinction is deliberate in the design
 * and worth keeping — a grid is for browsing by picture, a list is for scanning
 * results you asked for, and search is the second thing.
 *
 * The stats read "14.8k helped · 3.2k comments" rather than bare numbers beside
 * icons. On a results page the words carry the meaning; on a dense grid card
 * the icons do.
 */
export function ReviewListRow({ review }: { review: ReviewCardData }) {
  const headline = splitHeadline(review.title, review.product);

  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/reviews/${review.id}`}
        className="flex items-start gap-4 py-4 transition-colors hover:bg-[var(--line-hairline-10)]"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {review.avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={review.avatarUrl}
                alt=""
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
            <span className="truncate text-[12px] font-light text-[var(--text-primary)]">
              {review.username ? `@${review.username}` : review.author}
            </span>
            <TrustBadge
              levelName={review.trustLevel}
              stage={review.trustStage}
              score={review.trustScore}
              plain
              compact
            />
            <span className="text-[12px] font-extralight text-[var(--text-muted)]">
              · {review.ageLabel}
            </span>
          </div>

          <h2 className="mt-2 text-[14px] leading-snug text-[var(--text-primary)]">
            {headline.product ? (
              <>
                <span className="font-bold">{headline.product}</span>
                <span className="text-[var(--text-muted)]"> — </span>
                <span className="italic">{headline.rest}</span>
              </>
            ) : (
              <span className="font-bold">{review.title}</span>
            )}
          </h2>

          <p className="mt-2 text-[12px] font-light text-[var(--text-secondary)]">
            {review.upvotes} helped
            <span className="mx-1.5 opacity-50">·</span>
            {/* "1 comments" is the kind of thing that reads as machine output.
                upvotes/comments are pre-formatted strings ("14.8k"), so the
                singular only applies to a literal "1". */}
            {review.comments} {review.comments === "1" ? "comment" : "comments"}
          </p>
        </div>

        {/* 100px square, radius 16, pinned right. */}
        <div className="relative h-[100px] w-[100px] shrink-0 overflow-hidden rounded-[16px]">
          {review.imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={review.imageUrl}
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
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
