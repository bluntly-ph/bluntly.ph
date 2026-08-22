import type { Metadata } from "next";
import Link from "next/link";
import { CaretLeft, MagnifyingGlass, X } from "@phosphor-icons/react/dist/ssr";

import { ReviewListRow } from "@/components/review/ReviewListRow";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { CATEGORIES } from "@/lib/landing-data";
import { getUser } from "@/lib/dal";
import { searchReviews } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "Search — bluntly",
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; category?: string; from?: string }>;
}) {
  const { q = "", category, from } = await searchParams;
  const activeCategory = CATEGORIES.find((c) => c.slug === category);
  const searching = Boolean(q.trim() || category);
  // Arrived by tapping a tile on /categories. That makes /categories the
  // meaningful "up" destination — both for the back link and for "All", which
  // otherwise dead-ends on /search with no route back (BUG-011).
  const fromCategories = from === "categories";
  const categoryQuery = fromCategories ? "&from=categories" : "";

  // Parallel: the viewer and the results are independent (see app/page.tsx).
  const [me, results] = await Promise.all([
    getUser().catch(() => null),
    searchReviews({ q, category, limit: 24 }),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;

  const heading = q
    ? `Results for “${q}”`
    : activeCategory
      ? activeCategory.label
      : "Trending reviews";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      {/* `flex flex-col` so the empty state below can claim the leftover height.
          Without it a no-results page leaves a tall blank band and the footer
          reads as having "ridden up" into the middle of the screen (BUG-005). */}
      {/* 52rem, not the 72rem the browsing pages use. A results list is read,
          not scanned by picture: at full width the title sat hard left and its
          thumbnail was stranded ~600px away at the right edge, and nothing tied
          the two together. Narrowing the column is what stops this reading as a
          phone layout stretched to fill a monitor. */}
      <main className="mx-auto flex w-full max-w-[52rem] flex-1 flex-col px-6 py-8 lg:py-10">
        {fromCategories ? (
          <Link
            href="/categories"
            className="mb-5 inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <CaretLeft size={16} /> All categories
          </Link>
        ) : null}

        <form action="/search" role="search" className="relative max-w-[40rem]">
          <MagnifyingGlass
            size={20}
            className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Search products, reviews, or ask a question"
            aria-label="Search"
            // 56px at radius 32 with a #323232 hairline, as drawn — it was a
            // 48px raised white card. Search is this page's subject, so the
            // frame gives it more height than the landing's.
            className="h-14 w-full rounded-[32px] border border-[var(--base-gray-600)] bg-[var(--surface-app)] pl-12 pr-12 text-[16px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--accent-primary)]"
          />
          {q ? (
            <Link
              href="/search"
              aria-label="Clear search"
              className="absolute right-3 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
            >
              <X size={20} />
            </Link>
          ) : null}
        </form>

        {/* Category chips.
            A horizontal scroller is right on a phone, where the row is wider
            than the screen and swiping is natural. On desktop it was the wrong
            component entirely: the strip kept `w-max` and `overflow-x-auto`, so
            the last categories were clipped mid-word at the container edge with
            only a hidden scrollbar to reach them — fourteen categories, four of
            them unreachable without knowing to drag. There is room to wrap at
            `lg`, so it wraps. */}
        <div className="-mx-6 mt-5 overflow-x-auto px-6 [scrollbar-width:none] lg:mx-0 lg:overflow-x-visible lg:px-0">
          <ul className="flex w-max gap-2 lg:w-auto lg:flex-wrap lg:gap-y-2.5">
            <li>
              <Link
                href={fromCategories ? "/categories" : "/search"}
                className={chip(!category && !q)}
              >
                All
              </Link>
            </li>
            {CATEGORIES.filter((c) => c.slug !== "trending").map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/search?category=${c.slug}${categoryQuery}`}
                  className={chip(category === c.slug)}
                >
                  {c.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <h1 className="mt-8 text-[20px] font-bold text-[var(--text-primary)]">
          {heading}
        </h1>

        {results === null ? (
          <Unavailable what="reviews" />
        ) : results.length > 0 ? (
          // A list, not a grid — see ReviewListRow. Each row's title is an h2,
          // following the page h1 directly with no section heading between.
          <ul className="mt-3 border-t border-[var(--line-hairline-10)]">
            {results.map((r) => (
              <ReviewListRow key={r.id} review={r} />
            ))}
          </ul>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
            <MagnifyingGlass size={40} className="text-[var(--text-muted)]" />
            <p className="mt-4 text-[16px] font-semibold text-[var(--text-primary)]">
              {searching ? "No reviews found" : "Find the product you bought"}
            </p>
            <p className="mt-1 max-w-[22rem] text-[14px] text-[var(--text-secondary)]">
              {searching
                ? "Try a different product name, brand, or category."
                : "No need for the exact model. Just type what you know."}
            </p>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function chip(active: boolean): string {
  return [
    "inline-flex whitespace-nowrap rounded-[var(--radius-md)] px-3.5 py-1.5 text-[13px] font-medium capitalize",
    active
      ? "bg-[var(--accent-primary)] text-white"
      : "bg-[var(--surface-card)] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--text-primary)]",
  ].join(" ");
}
