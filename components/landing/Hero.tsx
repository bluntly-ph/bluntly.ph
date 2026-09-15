import { ArrowRight, DotOutline, MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { FEATURED_REVIEW } from "@/lib/landing-data";
import type { FeaturedData } from "@/lib/reviews";

import { FeaturedReviewCard } from "./FeaturedReviewCard";

/**
 * Landing hero, built to Figma "Mobile Landing Page" (1902:1504), read from the
 * file on 2026-09-14.
 *
 * Phone values, status bar excluded: the frame's own graph-paper image ("image
 * 15") as a 350x568 crop at 10%; copy 32px under the 72px bar — 32px SemiBold
 * with the period in brand orange, a 12px Light line at 70% ink 4px below; 32px
 * down, a 56px field with a 10% hairline, a 20px magnifier at 30% ink 14px in,
 * the 12px Light placeholder 44px in, and a 32px orange disc 8px from the right
 * with a 20px arrow; 44px down, the tilted review card group, 450px tall because
 * its two annotation pills sit below the card — "Earned" 30px under it at the
 * right, the question 218px under it at the left.
 *
 * From `md` up there is no frame: the two-column split starts at 768px, and the
 * pills sit on the card. The split used to wait for 1024px while the header had
 * already switched to its desktop form, stranding a narrow column in a wide
 * shell (QA's 768px pass).
 */
export function Hero({ featured }: { featured: FeaturedData }) {
  return (
    // `overflow-x-clip`: the tilted stack reaches the phone's right edge, and a
    // pixel past it must not become a sideways scroll.
    <section className="relative overflow-x-clip">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-4 top-[-6px] h-[568px] w-[350px] bg-[url('/figma/landing/hero-grid.png')] bg-[length:100%_100%] opacity-10 md:hidden"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 hidden [mask-image:linear-gradient(to_bottom,black,transparent)] md:block"
        style={{
          backgroundImage:
            "linear-gradient(rgba(32,32,32,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(32,32,32,0.05) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      <div className="relative mx-auto grid w-full max-w-[72rem] gap-11 px-4 pt-8 sm:px-6 md:grid-cols-2 md:items-center md:gap-8 md:px-8 md:py-14 lg:min-h-[86vh] lg:gap-16 lg:px-10 lg:py-20">
        <div className="animate-fade-up">
          {/* Desktop scales the same type up rather than restyling it, so the
              web version stays the mobile design at a larger size. */}
          <h1 className="text-[32px] font-semibold leading-[normal] text-[var(--text-primary)] md:text-[40px] lg:text-[56px]">
            Finally.
            <br />
            Honest reviews<span className="text-[var(--accent-primary)]">.</span>
          </h1>
          <p className="mt-1 text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)] lg:text-[14px] lg:leading-normal">
            No sponsorships. No bias. Ever.
          </p>

          {/* Ask-anything search — posts to the search page. */}
          <form action="/search" role="search" className="relative mt-8 max-w-[34rem]">
            <MagnifyingGlass
              size={20}
              className="pointer-events-none absolute left-[14px] top-1/2 -translate-y-1/2 text-[var(--line-hairline-30)]"
            />
            <input
              type="search"
              name="q"
              placeholder="Search or ask anything"
              aria-label="Search or ask anything"
              className="h-14 w-full rounded-[32px] border border-[rgba(32,32,32,0.1)] bg-[var(--surface-app)] pl-11 pr-12 text-[12px] font-light text-[var(--text-primary)] outline-none placeholder:text-[rgba(32,32,32,0.4)] focus-visible:border-[var(--accent-primary)] lg:text-[14px]"
            />
            <button
              type="submit"
              aria-label="Search"
              className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-[var(--accent-primary)] text-[var(--text-on-brand)] hover:bg-[var(--accent-primary-strong)]"
            >
              <ArrowRight size={20} />
            </button>
          </form>
        </div>

        <div className="animate-fade-up delay-2 relative mx-auto h-[450px] w-full max-w-[358px] md:h-auto md:max-w-[26rem] md:pb-6 md:pt-4">
          <FeaturedReviewCard featured={featured} />
          {/* Anchored to the card's right edge, not to a fixed left offset: the
              frame's x226 puts the pill's right edge 4px past the 358px column,
              and that relationship — not the 226 — is what holds on a 360 or
              375px phone. */}
          <span className="absolute right-[-4px] top-[238px] z-10 inline-flex h-6 items-center whitespace-nowrap rounded-[12px] bg-[var(--accent-primary)] pl-1 pr-3 text-[10px] leading-none text-[var(--text-on-brand)] shadow-[var(--shadow-sheet)] md:left-auto md:right-0 md:top-0">
            <DotOutline size={16} aria-hidden="true" />
            {FEATURED_REVIEW.earned}
          </span>
          <span className="absolute left-[11px] top-[426px] z-10 inline-flex h-6 items-center whitespace-nowrap rounded-[12px] bg-[var(--surface-app)] pl-1 pr-3 text-[10px] leading-none text-[var(--text-primary)] shadow-[var(--shadow-sheet)] md:bottom-0 md:left-2 md:top-auto">
            <DotOutline size={16} aria-hidden="true" className="text-[var(--accent-primary)]" />
            &ldquo;{FEATURED_REVIEW.question}&rdquo;
          </span>
        </div>
      </div>
    </section>
  );
}

export default Hero;
