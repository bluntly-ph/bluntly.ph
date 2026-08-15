import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { FEATURED_REVIEW } from "@/lib/landing-data";
import type { FeaturedData } from "@/lib/reviews";

import { FeaturedReviewCard } from "./FeaturedReviewCard";

/**
 * Landing hero — "Finally. Honest reviews." with the ask-anything search bar and
 * the featured review floating over a faint grid. Sized to fill the first screen
 * on desktop; mobile stacks copy → search → card with room to breathe.
 *
 * The two-column split starts at `md` (768px), not `lg`. It used to wait for
 * 1024px while the container was already 72rem wide and the header had switched
 * to its desktop form at `md`, so a tablet got a single narrow column stranded
 * inside a wide shell — the "dead space on the right" in QA's 768px pass, which
 * landscape phones hit as well.
 */
export function Hero({ featured }: { featured: FeaturedData }) {
  return (
    <section className="relative">
      {/* Faint graph-paper grid, fading out toward the bottom, as drawn. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 [mask-image:linear-gradient(to_bottom,black,transparent)]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(32,32,32,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(32,32,32,0.05) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      <div className="relative mx-auto grid w-full max-w-[72rem] gap-12 px-6 py-14 md:grid-cols-2 md:items-center md:gap-8 md:px-8 lg:min-h-[86vh] lg:gap-16 lg:px-10 lg:py-20">
        <div className="animate-fade-up">
          {/* 32px SemiBold with the period in brand orange, per the Page 1
              frame. It was 34px bold — a heavier, larger voice than drawn.
              Desktop scales the same type up rather than restyling it, so the
              web version stays the mobile design at a larger size. */}
          <h1 className="text-[32px] font-semibold leading-[normal] text-[var(--text-primary)] md:text-[40px] lg:text-[56px]">
            Finally.
            <br />
            Honest reviews<span className="text-[var(--accent-primary)]">.</span>
          </h1>
          <p className="mt-1 text-[12px] font-light tracking-[0.144px] text-[rgba(32,32,32,0.7)] lg:text-[14px]">
            No sponsorships. No bias. Ever.
          </p>

          {/* Ask-anything search — posts to the search page. */}
          <form action="/search" role="search" className="relative mt-8 max-w-[34rem]">
            <MagnifyingGlass
              size={20}
              className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            />
            <input
              type="search"
              name="q"
              placeholder="Search or ask anything"
              aria-label="Search or ask anything"
              // Sits on the page ground with a hairline, not a raised white
              // card — the frame draws it flush at 48px / radius 32, and the
              // shadow was inventing a depth the design does not have.
              className="h-12 w-full rounded-[32px] border border-[rgba(32,32,32,0.1)] bg-[var(--surface-app)] pl-11 pr-12 text-[12px] font-light text-[var(--text-primary)] outline-none placeholder:text-[rgba(32,32,32,0.4)] focus-visible:border-[var(--accent-primary)] lg:text-[14px]"
            />
            <button
              type="submit"
              aria-label="Search"
              className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-strong)]"
            >
              <ArrowRight size={18} weight="bold" />
            </button>
          </form>
        </div>

        {/* Featured review with the two floating chips. */}
        <div className="animate-fade-up delay-2 relative mx-auto w-full max-w-[26rem] pt-8 md:pt-0">
          {/* Sits *on* the card it belongs to (BUG-004). It was offset far
              enough above to read as a separate floating object with a gap
              between the two; 10px regular, overlapping the top edge. */}
          <span className="absolute -top-3 right-3 z-10 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-3 py-1 text-[10px] font-normal text-white shadow-[var(--shadow-card)]">
            {FEATURED_REVIEW.earned}
          </span>
          <FeaturedReviewCard featured={featured} />
          <span className="absolute -bottom-4 left-2 z-10 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-3 py-1.5 text-[12px] font-medium text-[var(--text-primary)] shadow-[var(--shadow-card)] outline outline-1 outline-[var(--line-hairline-10)]">
            &ldquo;{FEATURED_REVIEW.question}&rdquo;
          </span>
        </div>
      </div>
    </section>
  );
}

export default Hero;
