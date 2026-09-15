import Image from "next/image";
import Link from "next/link";
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
 */
export function FeaturedReviewCard({ featured }: { featured: FeaturedData }) {
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
    </div>
  );
}

export default FeaturedReviewCard;
