import Image from "next/image";
import Link from "next/link";
import { ArrowFatUp, ChatCircle, DotOutline, ImageSquare } from "@phosphor-icons/react/dist/ssr";

import type { ReviewCardData } from "@/lib/landing-data";
import { LAZY, type ImageHints } from "@/lib/list-image-hints";

/**
 * The review card on the landing rail and the profile grids: Figma
 * "FeaturedReviewCard" (6874:660), 188x280. Read 2026-09-14.
 *
 * A 188px square photo on #e1e1e1 with a 48px top scrim (8% black fading out,
 * 1px blur); the 24px avatar 12px in, with the author and age in 12px Regular
 * --text-on-brand on the scrim, split by a 12px DotOutline. Under it a 92px body
 * outlined on three sides at 10% ink: the title in 12px Regular on an 18px line
 * across two lines, and at the foot the upvote and comment counts in 12px Light
 * at 70% ink, each followed by its 12px glyph.
 *
 * From `md` up the grid sets the width, and the body grows with its content.
 */
export function ReviewCard({
  review,
  className = "",
  headingLevel = 3,
  imageHints = LAZY,
}: {
  review: ReviewCardData;
  /** How the photo loads: see lib/list-image-hints.ts. Lazy unless the rail says it is on screen. */
  imageHints?: ImageHints;
  className?: string;
  /**
   * Where this card's title sits in the page outline.
   *
   * Defaults to 3, which is right wherever the grid follows a section heading
   * ("What people are reading", "Your reviews"). A grid directly under the page
   * h1 passes 2, so heading navigation does not skip a level.
   */
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <Link
      href={`/reviews/${review.id}`}
      className={[
        // `relative` contains the sr-only labels: absolutely positioned, they
        // otherwise resolve against the page, escape the rail's scroller from
        // the off-screen cards, and widen the whole document sideways.
        "group relative flex flex-col rounded-[12px] text-[var(--text-primary)] no-underline",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]",
        className,
      ].join(" ")}
    >
      <div className="relative aspect-square w-full overflow-hidden rounded-t-[12px] bg-[#e1e1e1]">
        {review.imageUrl ? (
          /* A reviewer's own photo; the feed filters out the synthetic seed
             URLs. The card is a fixed rail card, so `sizes` is a fixed 24rem:
             the smallest exact Next candidate that still covers the box after an
             object-cover crop of a 1.9:1 source. */
          <Image
            src={review.imageUrl}
            alt=""
            fill
            sizes="24rem"
            loading={imageHints.loading}
            fetchPriority={imageHints.fetchPriority}
            className="object-cover transition-transform duration-[var(--duration-base)] group-hover:scale-[1.03]"
          />
        ) : (
          <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
            <ImageSquare size={30} weight="light" className="text-[var(--base-gray-400)]" />
          </div>
        )}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-12 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.08),rgba(0,0,0,0))] backdrop-blur-[1px]"
        />
        {/* --text-on-brand reads over a photo under the scrim; over the plain
            #e1e1e1 placeholder it would vanish, so that case keeps ink. The
            frame's photo is a dark lifestyle shot; real product photos are
            often on white, where the 8% scrim leaves white text unreadable
            (seen 2026-09-17 on the landing rail), so the byline carries a soft
            shadow that is invisible on a dark photo and legible on a light one. */}
        <div
          className={`absolute left-3 top-3 flex items-center gap-2 text-[12px] leading-none ${
            review.imageUrl
              ? "text-[var(--text-on-brand)] [text-shadow:0_1px_2px_rgba(0,0,0,0.55)]"
              : "text-[var(--text-primary)]"
          }`}
        >
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
              className="h-6 w-6 shrink-0 rounded-full"
              style={{ background: `hsl(${review.authorHue} 55% 55%)` }}
            />
          )}
          <span className="flex items-center gap-1 whitespace-nowrap">
            {review.author}
            <DotOutline size={12} aria-hidden="true" />
            {review.ageLabel}
          </span>
        </div>
      </div>

      <div className="flex h-[92px] flex-col rounded-b-[12px] border-x border-b border-[var(--line-hairline-10)] px-3 pb-3 pt-3 md:h-auto md:min-h-[92px]">
        <Heading className="line-clamp-2 text-[12px] font-normal leading-[18px]">
          {review.product ? `${review.product} - ${review.title}` : review.title}
        </Heading>
        <p className="mt-auto flex items-center gap-1 pt-2 text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">
          <span className="inline-flex items-center gap-1">
            {review.upvotes}
            <ArrowFatUp size={12} weight="fill" aria-hidden="true" />
            <span className="sr-only">upvotes</span>
          </span>
          <DotOutline size={12} aria-hidden="true" />
          <span className="inline-flex items-center gap-1">
            {review.comments || "0"}
            <ChatCircle size={12} aria-hidden="true" />
            <span className="sr-only">comments</span>
          </span>
        </p>
      </div>
    </Link>
  );
}

export default ReviewCard;
