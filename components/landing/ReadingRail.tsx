import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

import { ReviewCard } from "@/components/review/ReviewCard";
import { firstImageIndex, listImageHints } from "@/lib/list-image-hints";
import { CATEGORIES, type ReviewCardData } from "@/lib/landing-data";

/**
 * "What people are reading", built to Figma "SectionHeader" (6884:871) and the
 * rail in "Mobile Landing Page" (1902:1504). Read 2026-09-14.
 *
 * Phone: 52px under the hero group; "Discover" and "Browse all" in 12px
 * Regular trust blue (the link at 90%, with a 12px arrow), the heading 4px
 * below in 20px Medium; 20px down, the category tabs — 20px glyphs with 12px
 * Light labels 4px after them, 24px apart, the current one in brand orange;
 * 24px down, 188x280 cards 8px apart. From `md` up there is no frame, so the
 * cards become a grid.
 */
export function ReadingRail({ reviews }: { reviews: ReviewCardData[] }) {
  return (
    <section className="bg-[var(--surface-app)] md:border-t md:border-[var(--border-subtle)]">
      <div className="mx-auto w-full max-w-[72rem] px-4 pt-[52px] sm:px-6 md:py-16 lg:px-10 lg:py-24">
        <div className="flex items-center justify-between">
          <span className="text-[12px] leading-none text-[var(--accent-trust)]">Discover</span>
          {/* -my-2.5 py-2.5 grows the touch target to 32px without moving
              anything: the padding is added and pulled back out of flow. */}
          <Link
            href="/search"
            className="-my-2.5 inline-flex items-center gap-1 py-2.5 text-[12px] leading-none text-[color-mix(in_srgb,var(--accent-trust)_90%,transparent)] hover:underline"
          >
            Browse all
            <ArrowRight size={12} />
          </Link>
        </div>
        <h2 className="mt-1 text-[20px] font-medium leading-none text-[var(--text-primary)]">
          What people are reading
        </h2>

        {/* Scrolls sideways only. `overflow-x: auto` makes overflow-y compute to
            auto too, and each tab's 44px target (-my-3 py-3) spilled 12px below
            the 20px row, so the rail itself scrolled vertically and clipped its
            icons (production, 2026-09-17, every width). The 12px padding holds
            the targets inside the box — mt-2 + py-3 keeps the row where mt-5
            put it, -mb-3 takes the padding back out — and overflow-y-hidden
            stops any remainder. */}
        <div className="-mx-4 -mb-3 mt-2 overflow-x-auto overflow-y-hidden px-4 py-3 [scrollbar-width:none] sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
          <ul className="flex w-max gap-6">
            {CATEGORIES.map((c, i) => {
              const Icon = c.icon;
              const active = i === 0;
              return (
                <li key={c.slug}>
                  <Link
                    href={active ? "/search" : `/search?category=${c.slug}`}
                    className={[
                      // The row is 20px as drawn; -my-3 py-3 gives each tab a
                      // 44px target without moving it.
                      // `flex`, not `inline-flex`: an inline box sat on the li's
                      // line box and pushed the cards 7px down.
                      "-my-3 flex min-h-[44px] items-center gap-1 whitespace-nowrap py-3 text-[12px] font-light leading-none",
                      active
                        ? "text-[var(--accent-primary)]"
                        : "text-[var(--text-primary)] hover:text-[var(--accent-primary)]",
                    ].join(" ")}
                  >
                    <Icon size={20} />
                    {c.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        {/* scroll-px keeps snapping on the 16px gutter; without it the first
            card snapped flush to the screen edge. */}
        <div className="-mx-4 mt-6 flex snap-x scroll-px-4 gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:-mx-6 sm:scroll-px-6 sm:px-6 md:mx-0 md:mt-8 md:grid md:grid-cols-3 md:gap-6 md:overflow-visible md:px-0 lg:grid-cols-5">
          {/* The first two 188px cards are on a phone screen at arrival, and
              with a photo one of them is the landing page's LCP element once
              the hero's graph paper stopped being an image (Lighthouse on the
              candidate, 2026-09-17: a lazy rail photo was the LCP). */}
          {reviews.map((r, i, all) => (
            <ReviewCard
              key={r.id}
              review={r}
              imageHints={listImageHints(i, firstImageIndex(all, (x) => Boolean(x.imageUrl)), 2)}
              className="w-[188px] shrink-0 snap-start md:w-auto"
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export default ReadingRail;
