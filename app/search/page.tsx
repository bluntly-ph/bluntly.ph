import type { Metadata } from "next";
import Link from "next/link";
import { MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { ReviewCard } from "@/components/review/ReviewCard";
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
  searchParams: Promise<{ q?: string; category?: string }>;
}) {
  const { q = "", category } = await searchParams;
  const activeCategory = CATEGORIES.find((c) => c.slug === category);
  const searching = Boolean(q.trim() || category);

  let user: HeaderUser = null;
  try {
    const me = await getUser();
    user = me ? { username: me.username, avatarUrl: me.avatar_url } : null;
  } catch {
    user = null;
  }

  const results = await searchReviews({ q, category, limit: 24 });

  const heading = q
    ? `Results for “${q}”`
    : activeCategory
      ? activeCategory.label
      : "Trending reviews";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[72rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
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
            className="h-12 w-full rounded-[var(--radius-pill)] bg-[var(--surface-card)] pl-12 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
          />
        </form>

        {/* Category chips */}
        <div className="-mx-6 mt-5 overflow-x-auto px-6 [scrollbar-width:none] lg:mx-0 lg:px-0">
          <ul className="flex w-max gap-2">
            <li>
              <Link
                href="/search"
                className={chip(!category && !q)}
              >
                All
              </Link>
            </li>
            {CATEGORIES.filter((c) => c.slug !== "trending").map((c) => (
              <li key={c.slug}>
                <Link href={`/search?category=${c.slug}`} className={chip(category === c.slug)}>
                  {c.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <h1 className="mt-8 text-[20px] font-bold text-[var(--text-primary)]">
          {heading}
        </h1>

        {results.length > 0 ? (
          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 md:gap-6 lg:grid-cols-4">
            {results.map((r) => (
              <ReviewCard key={r.id} review={r} />
            ))}
          </div>
        ) : (
          <div className="mt-16 flex flex-col items-center text-center">
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
