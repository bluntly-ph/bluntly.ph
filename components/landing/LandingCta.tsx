import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

/** The "Stop guessing. Start knowing." conversion screen. */
export function LandingCta() {
  return (
    <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-app)]">
      <div className="mx-auto flex w-full max-w-[72rem] items-center px-6 py-16 lg:min-h-[60vh] lg:px-10 lg:py-24">
        <div className="relative w-full overflow-hidden rounded-[var(--radius-md)] bg-[var(--accent-primary)] px-6 py-10 text-white lg:px-14 lg:py-16">
          {/* Decorative soft circles, echoing the frame. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-white/10"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-24 left-10 h-56 w-56 rounded-full bg-black/5"
          />

          <div className="relative max-w-[40rem]">
            <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-white/80">
              Ready?
            </span>
            <h2 className="mt-3 text-[30px] font-bold leading-[1.1] lg:text-[44px]">
              Stop guessing.
              <br />
              <span className="font-semibold italic">Start knowing.</span>
            </h2>
            <p className="mt-4 max-w-[32rem] text-[15px] text-white/90">
              Join Filipinos making smarter purchases and the reviewers earning from
              honest opinions.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/search"
                className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-white px-6 py-3 text-[14px] font-semibold text-[var(--text-primary)] hover:bg-[var(--base-gray-100)]"
              >
                Find a review
                <ArrowRight size={16} weight="bold" />
              </Link>
              <Link
                href="/reviews/new"
                className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-white/70 px-6 py-3 text-[14px] font-semibold text-white hover:bg-white/10"
              >
                Write &amp; Earn
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default LandingCta;
