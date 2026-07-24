import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

import { ReviewCard } from "@/components/review/ReviewCard";
import { CATEGORIES, type ReviewCardData } from "@/lib/landing-data";

/**
 * "What people are reading" — the discover eyebrow, the horizontally scrolling
 * category tabs, and a rail of review cards (a horizontal scroll-snap strip on
 * mobile; a grid on desktop). Set on its own band with generous space so it
 * reads as a distinct screen from the hero.
 */
export function ReadingRail({ reviews }: { reviews: ReviewCardData[] }) {
  return (
    <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-app)]">
      <div className="mx-auto w-full max-w-[72rem] px-6 py-16 lg:px-10 lg:py-24">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium uppercase tracking-[0.1em] text-[var(--text-muted)]">
            Discover
          </span>
          <Link
            href="/search"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            Browse all
            <ArrowRight size={14} />
          </Link>
        </div>
        <h2 className="mt-1 text-[26px] font-bold text-[var(--text-primary)] lg:text-[32px]">
          What people are reading
        </h2>

        {/* Category tabs — horizontal scroll on any width. */}
        <div className="-mx-6 mt-6 overflow-x-auto px-6 [scrollbar-width:none] lg:mx-0 lg:px-0">
          <ul className="flex w-max gap-6">
            {CATEGORIES.map((c, i) => {
              const Icon = c.icon;
              const active = i === 0;
              return (
                <li key={c.slug}>
                  <Link
                    href={active ? "/search" : `/search?category=${c.slug}`}
                    className={[
                      "inline-flex items-center gap-1.5 whitespace-nowrap text-[14px]",
                      active
                        ? "font-semibold text-[var(--accent-primary)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <Icon size={20} weight={active ? "fill" : "regular"} />
                    {c.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Cards: scroll-snap strip on mobile, grid from md up. */}
        <div className="-mx-6 mt-8 flex snap-x gap-4 overflow-x-auto px-6 pb-2 [scrollbar-width:none] md:mx-0 md:grid md:grid-cols-3 md:gap-6 md:overflow-visible md:px-0 lg:grid-cols-5">
          {reviews.map((r) => (
            <ReviewCard
              key={r.id}
              review={r}
              className="w-[62vw] max-w-[200px] shrink-0 snap-start md:w-auto md:max-w-none"
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export default ReadingRail;
