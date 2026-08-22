import Image from "next/image";
import Link from "next/link";
import {
  ChatCircle,
  HandsClapping,
  ImageSquare,
  SealCheck,
  Star,
} from "@phosphor-icons/react/dist/ssr";

import { TrustBadge } from "@/components/ui/TrustBadge";
import type { FeedCardData } from "@/lib/reviews";

/**
 * The same three verdict styles `ReviewDetail` uses, deliberately identical.
 *
 * A verdict that is green on the feed and a different green on the review it
 * links to reads as two different claims. If these ever need to change, change
 * both — they are the platform's central judgement and the one thing a reader
 * is meant to recognise at a glance.
 */
const VERDICT: Record<string, { label: string; className: string }> = {
  yes_absolutely: {
    label: "Yes, absolutely",
    className:
      "bg-[color-mix(in_srgb,var(--accent-success)_14%,transparent)] text-[var(--accent-success)]",
  },
  it_depends: {
    label: "It depends",
    className:
      "bg-[color-mix(in_srgb,var(--accent-star)_18%,transparent)] text-[var(--base-ink-700)]",
  },
  hard_pass: {
    label: "Hard pass",
    className:
      "bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] text-[var(--accent-danger)]",
  },
};

/**
 * One review in the browsing feed.
 *
 * Deliberately not `ReviewCard`, which is a square image tile built for a grid:
 * a feed row has to answer "is this worth opening?" without being opened, and a
 * cropped photo plus a title does not. So this leads with the verdict, the
 * rating and who is speaking — the three things that decide it — and gives the
 * writing an excerpt rather than the whole body.
 *
 * The full review stays on `/reviews/[id]`. Nothing here links anywhere else,
 * so the whole row is one target rather than a card containing rival links.
 */
export function FeedCard({
  review,
  priority = false,
}: {
  review: FeedCardData;
  /** First card only: its thumbnail is the above-the-fold LCP candidate. */
  priority?: boolean;
}) {
  const verdict = VERDICT[review.verdict] ?? VERDICT.it_depends;

  return (
    <article className="border-b border-[var(--border-subtle)] last:border-0">
      <Link
        href={`/reviews/${review.id}`}
        className="group flex gap-4 py-5 transition-colors duration-[var(--duration-fast)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] sm:gap-5"
      >
        {/* Thumbnail. Fixed square so a long title cannot stretch the row and a
            short one cannot collapse it — the column edge stays put down the
            whole feed, which is most of what makes a list scannable. */}
        <span className="relative block h-20 w-20 shrink-0 overflow-hidden rounded-[var(--radius-sm)] sm:h-24 sm:w-24">
          {review.imageUrl ? (
            /* 80/96 px box, so `sizes` says so — the stored object is a
               full-size photograph and would otherwise be fetched at the
               browser's 100vw default. */
            <Image
              src={review.imageUrl}
              alt=""
              fill
              sizes="(min-width: 640px) 192px, 160px"
              priority={priority}
              className="object-cover"
            />
          ) : (
            <span
              aria-hidden="true"
              className="absolute inset-0 grid place-items-center"
              style={{
                background: `linear-gradient(150deg, hsl(${review.imageHue} 42% 74%), hsl(${review.imageHue + 24} 38% 55%))`,
              }}
            >
              <ImageSquare size={24} weight="light" className="text-white/55" />
            </span>
          )}
        </span>

        <span className="min-w-0 flex-1">
          {/* What is being reviewed, before what was concluded about it. */}
          {review.product ? (
            <span className="block truncate text-[12px] text-[var(--text-muted)]">
              {review.product}
              {review.category ? (
                <span className="capitalize"> · {review.category}</span>
              ) : null}
            </span>
          ) : null}

          <h3 className="mt-0.5 text-[15px] font-semibold leading-snug text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] sm:text-[16px]">
            {review.title}
          </h3>

          <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span
              className={`inline-flex items-center rounded-[var(--radius-pill)] px-2.5 py-1 text-[12px] font-semibold ${verdict.className}`}
            >
              {verdict.label}
            </span>
            <span
              className="inline-flex items-center gap-0.5"
              aria-label={`${review.stars} out of 5 stars`}
            >
              {Array.from({ length: 5 }, (_, i) => (
                <Star
                  key={i}
                  size={14}
                  weight={i < review.stars ? "fill" : "regular"}
                  className={
                    i < review.stars
                      ? "text-[var(--accent-star)]"
                      : "text-[var(--base-gray-300)]"
                  }
                />
              ))}
            </span>
            {review.verified ? (
              <span className="inline-flex items-center gap-1 text-[12px] text-[var(--accent-success)]">
                <SealCheck size={14} weight="fill" />
                Verified
              </span>
            ) : null}
          </span>

          {review.excerpt ? (
            <span className="mt-2 line-clamp-2 block text-[13px] font-light leading-[20px] text-[var(--text-secondary)]">
              {review.excerpt}
            </span>
          ) : null}

          <span className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-secondary)]">
              {review.username ? `@${review.username}` : review.author}
            </span>
            <TrustBadge
              levelName={review.trustLevel}
              stage={review.trustStage}
              score={review.trustScore}
              plain
            />
            <span className="inline-flex items-center gap-1">
              <HandsClapping size={13} />
              {review.helpful}
            </span>
            <span className="inline-flex items-center gap-1">
              <ChatCircle size={13} />
              {review.comments}
            </span>
            <span>{review.ageLabel}</span>
          </span>
        </span>
      </Link>
    </article>
  );
}

export default FeedCard;
