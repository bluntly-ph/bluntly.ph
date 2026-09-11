import Link from "next/link";
import { MagnifyingGlass, PencilSimpleLine } from "@phosphor-icons/react/dist/ssr";

import { SearchAutocomplete } from "@/components/search/SearchAutocomplete";
import { Logo } from "@/components/ui/Logo";
import { ProfileNavPanel } from "@/components/site/ProfileNavPanel";

export type HeaderUser = {
  username: string | null;
  avatarUrl: string | null;
} | null;

/**
 * The public site header — orange wordmark, search, and either the signed-in
 * avatar or a log-in affordance. Mobile is the frame (wordmark + search icon +
 * avatar); at `lg` it widens into a real top bar with an inline search field and
 * a "Write a review" call to action.
 */
export function SiteHeader({ user }: { user: HeaderUser }) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--surface-app)_85%,transparent)] backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-[72rem] items-center gap-4 px-6 md:h-[72px] md:px-10">
        <Link href="/" aria-label="bluntly home" className="text-[var(--accent-primary)]">
          <Logo height={22} label="bluntly" />
        </Link>

        {/* Desktop inline search */}
        <div className="ml-4 hidden w-full max-w-[32rem] flex-1 md:block">
          <SearchAutocomplete
            inputClassName="h-10 w-full rounded-[var(--radius-pill)] bg-[var(--surface-card)] pl-11 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[inset_0_0_0_1px_var(--accent-primary)]"
          />
        </div>

        <div className="ml-auto flex items-center gap-2 md:gap-3">
          <Link
            href="/search"
            aria-label="Search"
            className="grid h-10 w-10 place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] md:hidden"
          >
            <MagnifyingGlass size={24} />
          </Link>

          {/* First in the row: for a reader who is already sold, browsing is
              the thing they came to do. `/` stays the landing page. */}
          <Link
            href="/feed"
            className="hidden min-h-[44px] items-center text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:inline-flex"
          >
            Feed
          </Link>

          <Link
            href="/categories"
            className="hidden min-h-[44px] items-center text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:inline-flex"
          >
            Categories
          </Link>

          <Link
            href="/questions"
            className="hidden min-h-[44px] items-center text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:inline-flex"
          >
            Q&amp;A
          </Link>

          <Link
            href="/requests"
            className="hidden min-h-[44px] items-center text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:inline-flex"
          >
            Requests
          </Link>

          <Link
            href="/reviews/new"
            className="hidden items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[var(--accent-primary-strong)] md:inline-flex"
          >
            <PencilSimpleLine size={16} weight="bold" />
            Write a review
          </Link>

          <ProfileNavPanel user={user} />
        </div>
      </div>
    </header>
  );
}

export default SiteHeader;
