import type { Metadata } from "next";
import Link from "next/link";
import { HouseLine, MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Reviewer not found — bluntly",
};

/**
 * The 404 for a reviewer profile.
 *
 * The page used to render this copy inline and return 200. That is a soft 404:
 * `/u/{id}` accepts any id, so every made-up one was a real, indexable page,
 * and Next only injects `<meta name="robots" content="noindex">` for responses
 * that actually 404. The review and question routes already called
 * `notFound()`; this one had drifted.
 *
 * A segment-level `not-found` keeps the wording that fits here — the root one
 * talks about reviews being taken down — while the status code comes from
 * `notFound()` in the page.
 *
 * The message deliberately covers two cases at once. `getAuthorProfile`
 * returns null both for a reviewer who does not exist and for one with nothing
 * published yet, and collapsing them is the privacy-preserving answer: it
 * means this page cannot be used to test whether an account exists.
 */
export default function ReviewerNotFound() {
  return (
    <PageShell>
      <div className="flex flex-col items-center py-10 text-center lg:py-16">
        <p className="font-[family-name:var(--font-display)] text-[72px] leading-none text-[var(--accent-primary)] lg:text-[96px]">
          404
        </p>

        <h1 className="mt-4 text-[24px] font-bold text-[var(--text-primary)] lg:text-[30px]">
          Reviewer not found.
        </h1>
        <p className="mt-2 max-w-[26rem] text-[14px] leading-relaxed text-[var(--text-secondary)]">
          This reviewer has no published reviews yet, or the profile
          doesn&rsquo;t exist.
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
            Browse reviews
          </Link>
        </div>
      </div>
    </PageShell>
  );
}
