import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { DotOutline, DotsThree } from "@phosphor-icons/react/dist/ssr";

import { HonestyScore } from "@/components/ui/HonestyScore";
import type { FeaturedData } from "@/lib/reviews";

/**
 * The hero's headline review: Figma "ReviewCard" (7082:1414), the tilted card
 * whose landing styling the file calls canon. Read 2026-09-14.
 *
 * Geometry from the component's 375x209 box: three 358x172 layers — a brand
 * tint at 10% rotated +5deg, the same tint flat, and the card itself rotated
 * -5deg on top in --surface-app with the file's warm #bcaca6 shadow. Inside,
 * 12px padding and 8px gaps: a 28px avatar, the handle in 12px Light with a
 * 16px DotOutline before the Honesty Score, the age in 10px ExtraLight beneath;
 * the title in 12px Bold with the verdict in regular italic; the excerpt in
 * 12px Light on an 18px line; and a 24px DotsThree 12px from the top right.
 *
 * The overflow glyph is drawn as decoration: the whole card is one link, and a
 * second control inside it would nest interactive content.
 *
 * The two annotations belong to this composition, not to the page: the owner
 * corrected the hero in Figma on 2026-09-16 and asked for it copied one to one,
 * and the frame's own group (5446:5126, 375x209) places them against the card:
 *
 *   topRight     x244 y4   — "How noisy is it?", over the card's top-right
 *   bottomLeft   x0   y185 — "Earned ₱45.50 today", on the card's bottom-left
 *
 * Both are given as a share of that group, so they hold their relationship to
 * the card at any column width instead of drifting with the viewport.
 */
export function FeaturedReviewCard({
  featured,
  badgeTopRight,
  badgeBottomLeft,
}: {
  featured: FeaturedData;
  badgeTopRight?: ReactNode;
  badgeBottomLeft?: ReactNode;
}) {
  const handle = featured.username ?? featured.author;
  // The layers take the column's width rather than a fixed 358px: at 390 the
  // column IS 358px, so the frame is unchanged, and on a narrower phone (360,
  // 375) the stack narrows with it instead of running off the right edge.
  const layer = "absolute h-[172px] w-full rounded-[12px] bg-[rgba(239,88,33,0.1)]";

  return (
    <div className="relative h-[209px] w-full">
      <div aria-hidden="true" className={`${layer} left-[11px] top-[21px] rotate-[5deg]`} />
      <div aria-hidden="true" className={`${layer} left-[11px] top-5`} />

      <Link
        href={featured.id ? `/reviews/${featured.id}` : "/search"}
        // Hover eases the rotation rather than translating, so the card stays
        // seated in its stack.
        className="absolute left-[7px] top-[15px] flex h-[172px] w-full -rotate-[5deg] flex-col gap-2 overflow-hidden rounded-[12px] bg-[var(--surface-app)] p-3 text-[var(--text-primary)] no-underline shadow-[0px_4px_4px_0px_#bcaca6] transition-transform duration-[var(--duration-base)] hover:-rotate-[3deg]"
      >
        <div className="flex items-center gap-2 pr-8">
          {featured.avatarUrl ? (
            <Image
              src={featured.avatarUrl}
              alt=""
              width={28}
              height={28}
              className="h-7 w-7 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span
              aria-hidden="true"
              className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold text-white"
              style={{ background: `hsl(${featured.authorHue} 55% 55%)` }}
            >
              {featured.author.slice(0, 1).toUpperCase()}
            </span>
          )}
          <div className="flex min-w-0 flex-col">
            <p className="flex min-w-0 items-center text-[12px] font-light leading-4">
              <span className="truncate">{handle}</span>
              {/* Only for a real author: the offline sample has no score, and a
                  made-up one would be a decorative trust claim. */}
              {featured.trustScore ? (
                <>
                  <DotOutline size={16} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                  <HonestyScore
                    score={featured.trustScore}
                    levelName={featured.trust}
                    stage={featured.trustStage}
                  />
                </>
              ) : null}
            </p>
            <span className="text-[10px] font-extralight leading-[15px]">{featured.ageLabel}</span>
          </div>
        </div>

        {/* h2: this card sits directly under the page h1 in the hero. */}
        <h2 className="line-clamp-2 text-[12px] font-bold leading-[18px]">
          {featured.product ? (
            <>
              {featured.product} - <span className="font-normal italic">{featured.title}</span>
            </>
          ) : (
            featured.title
          )}
        </h2>
        <p className="line-clamp-3 text-[12px] font-light leading-[18px]">{featured.excerpt}</p>

        <DotsThree size={24} aria-hidden="true" className="absolute right-3 top-3" />
      </Link>

      {/* The card is rotated -5deg about its own centre, which lifts its
          top-right corner to roughly the composition's (right - 10, top): the
          same relationship at 320 as at 430, because the card's width follows
          the column. So the badge hangs off that corner — right-aligned to the
          composition and half a badge above its top edge — and it stays
          attached however wide the column gets. */}
      {/* x244 of the frame's 375-wide group is 16px in from its right edge. */}
      {badgeTopRight ? (
        <div className="pointer-events-none absolute right-[16px] top-[4px] z-10">{badgeTopRight}</div>
      ) : null}

      {/* y185 of 209, flush to the group's left edge: the pill's foot lands on
          the card's bottom edge, which is what the frame draws. */}
      {badgeBottomLeft ? (
        <div className="pointer-events-none absolute left-0 top-[185px] z-10">{badgeBottomLeft}</div>
      ) : null}
    </div>
  );
}

export default FeaturedReviewCard;
