import type { Metadata } from "next";
import Link from "next/link";
import { CaretLeft, ChatCircle, MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";

import { QuestionResultRow } from "@/components/search/QuestionResultRow";
import { SearchAutocomplete } from "@/components/search/SearchAutocomplete";
import { SearchTabs, type SearchTab } from "@/components/search/SearchTabs";
import { ReviewListRow } from "@/components/review/ReviewListRow";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { CATEGORIES } from "@/lib/landing-data";
import { getUser } from "@/lib/dal";
import { getQuestions } from "@/lib/qa";
import { searchReviews } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "Search — bluntly",
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; category?: string; from?: string; tab?: string }>;
}) {
  const { q = "", category, from, tab } = await searchParams;
  const activeTab: SearchTab = tab === "questions" ? "questions" : "reviews";
  const activeCategory = CATEGORIES.find((c) => c.slug === category);
  const searching = Boolean(q.trim() || category);
  // Arrived by tapping a tile on /categories. That makes /categories the
  // meaningful "up" destination — both for the back link and for "All", which
  // otherwise dead-ends on /search with no route back (BUG-011).
  const fromCategories = from === "categories";
  const categoryQuery = fromCategories ? "&from=categories" : "";

  // Parallel: the viewer and the results are independent (see app/page.tsx).
  // Only the active tab's results are fetched — the other tab is a separate URL
  // and will fetch its own when it is visited.
  const [me, results, questions] = await Promise.all([
    getUser().catch(() => null),
    activeTab === "reviews"
      ? searchReviews({ q, category, limit: 24 })
      : Promise.resolve(null),
    activeTab === "questions"
      ? getQuestions(undefined, { q, limit: 24 })
      : Promise.resolve(null),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;

  const heading = q
    ? `Results for “${q}”`
    : activeCategory
      ? activeCategory.label
      : activeTab === "questions"
        ? "Recent questions"
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

        {/* 56px at radius 32 with a #323232 hairline, as drawn — search is
            this page's subject, so it gets more height than the landing's. */}
        <div className="max-w-[40rem]">
          <SearchAutocomplete
            defaultValue={q}
            placeholder="Search products, reviews, or ask a question"
            showClear
            inputClassName="h-14 w-full rounded-[32px] border border-[var(--base-gray-600)] bg-[var(--surface-app)] pl-12 pr-12 text-[16px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--accent-primary)]"
          />
        </div>

        <SearchTabs active={activeTab} q={q} category={category} from={from} />

        {/* Category chips.
            A horizontal scroller is right on a phone, where the row is wider
            than the screen and swiping is natural. On desktop it was the wrong
            component entirely: the strip kept `w-max` and `overflow-x-auto`, so
            the last categories were clipped mid-word at the container edge with
            only a hidden scrollbar to reach them — fourteen categories, four of
            them unreachable without knowing to drag. There is room to wrap at
            `lg`, so it wraps. */}
        {/* Categories narrow reviews. They have no meaning for questions, so
            the row is not rendered on that tab rather than shown inert. */}
        {activeTab === "reviews" ? (
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
        ) : null}

        <h1 className="mt-8 text-[20px] font-bold text-[var(--text-primary)]">
          {heading}
        </h1>

        {activeTab === "questions" ? (
          questions === null ? (
            <Unavailable what="questions" />
          ) : questions.length > 0 ? (
            <ul className="mt-3 border-t border-[var(--line-hairline-10)]">
              {questions.map((question) => (
                <QuestionResultRow key={question.id} question={question} />
              ))}
            </ul>
          ) : (
            <EmptyResults
              icon={<ChatCircle size={40} className="text-[var(--text-muted)]" />}
              title={searching ? "No questions found" : "Ask about a product"}
              body={
                searching
                  ? "Try a different product name or wording."
                  : "Search for a product to see what buyers are asking about it."
              }
            />
          )
        ) : results === null ? (
          <Unavailable what="reviews" />
        ) : results.length > 0 ? (
          // A list, not a grid — see ReviewListRow. Each row's title is an h2,
          // following the page h1 directly with no section heading between.
          <ul className="mt-3 border-t border-[var(--line-hairline-10)]">
            {results.map((r, i) => (
              <ReviewListRow key={r.id} review={r} priority={i === 0} />
            ))}
          </ul>
        ) : (
          <EmptyResults
            icon={<MagnifyingGlass size={40} className="text-[var(--text-muted)]" />}
            title={searching ? "No reviews found" : "Find the product you bought"}
            body={
              searching
                ? "Try a different product name, brand, or category."
                : "No need for the exact model. Just type what you know."
            }
          />
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

/**
 * The shared empty state for both tabs — one component so "no reviews" and "no
 * questions" cannot drift apart in spacing or voice.
 */
function EmptyResults({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
      {icon}
      <p className="mt-4 text-[16px] font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 max-w-[22rem] text-[14px] text-[var(--text-secondary)]">{body}</p>
    </div>
  );
}
