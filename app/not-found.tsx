import type { Metadata } from "next";
import Link from "next/link";
import { HouseLine, MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Page not found — bluntly",
};

/**
 * The 404 (BUG-003).
 *
 * The root `not-found` catches unmatched URLs for the whole app, not just
 * `notFound()` calls, so this is what a mistyped address gets. It goes through
 * PageShell rather than standing alone: a visitor who lands here should keep the
 * header, their signed-in state, and the footer — a bare error page reads like
 * the site fell over, which is exactly the impression a review site can't afford.
 *
 * Two ways out, because "go home" is not always what the person wanted: the home
 * page, or search, which is where a dead review link most likely belongs.
 */
export default function NotFound() {
  return (
    <PageShell>
      <div className="flex flex-col items-center py-10 text-center lg:py-16">
        <p className="font-[family-name:var(--font-display)] text-[72px] leading-none text-[var(--accent-primary)] lg:text-[96px]">
          404
        </p>

        <h1 className="mt-4 text-[24px] font-bold text-[var(--text-primary)] lg:text-[30px]">
          This page doesn&rsquo;t exist.
        </h1>
        <p className="mt-2 max-w-[26rem] text-[14px] leading-relaxed text-[var(--text-secondary)]">
          The link may be broken, or the review may have been taken down. No
          sugarcoating it — there&rsquo;s nothing here.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 py-3 text-[14px] font-semibold text-white hover:bg-[var(--accent-primary-strong)]"
          >
            <HouseLine size={18} weight="fill" />
            Back home
          </Link>
          <Link
            href="/search"
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] px-6 py-3 text-[14px] font-semibold text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--line-hairline-30)] hover:bg-[var(--line-hairline-10)]"
          >
            <MagnifyingGlass size={18} />
            Search reviews
          </Link>
        </div>
      </div>
    </PageShell>
  );
}
