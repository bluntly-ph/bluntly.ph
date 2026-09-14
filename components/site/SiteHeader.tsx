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
 *
 * `showSearch={false}` drops the phone's search icon. The search page passes it:
 * its frames draw the wordmark and avatar only, because the page itself is the
 * search.
 */
export function SiteHeader({ user, showSearch = true }: { user: HeaderUser; showSearch?: boolean }) {
  return (
    // The phone bar is Figma "NavBar" Type=Landing (6884:817): 72px including a
    // 1px rule at 10% ink, the 78x24 wordmark 24px in, a 28px search glyph, and
    // the 40px avatar 24px from the right edge. Tablet and desktop keep their
    // full-width rule on the header itself.
    <header className="sticky top-0 z-30 bg-[color-mix(in_srgb,var(--surface-app)_85%,transparent)] backdrop-blur-md md:border-b md:border-[var(--border-subtle)]">
      <div className="mx-auto flex h-[72px] w-full max-w-[72rem] items-center gap-4 border-b border-[var(--line-hairline-10)] px-6 md:border-b-0 md:px-10">
        {/* `flex`: an inline link sits the 24px mark on a taller line box, 4px
            above the frame's y. */}
        <Link href="/" aria-label="bluntly home" className="flex text-[var(--accent-primary)]">
          <Logo height={24} label="bluntly" />
        </Link>

        {/* Desktop inline search */}
        <div className="ml-4 hidden w-full max-w-[32rem] flex-1 md:block">
          <SearchAutocomplete
            inputClassName="h-10 w-full rounded-[var(--radius-pill)] bg-[var(--surface-card)] pl-11 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[inset_0_0_0_1px_var(--accent-primary)]"
          />
        </div>

        {/* 14px between the search glyph's 40px target and the avatar puts the
            glyph at x278 and the avatar at x326, as drawn. */}
        <div className="ml-auto flex items-center gap-3.5 md:gap-3">
          {showSearch ? (
            <Link
              href="/search"
              aria-label="Search"
              className="grid h-10 w-10 place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] md:hidden"
            >
              <MagnifyingGlass size={28} />
            </Link>
          ) : null}

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
