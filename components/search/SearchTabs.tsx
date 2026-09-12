import Link from "next/link";

import { searchTabHref, type SearchTab } from "./search-tabs-model";

/**
 * The Reviews / Questions tab strip on /search.
 *
 * The design reference draws three tabs — Reviews, Questions, Sellers.
 *
 * SELLERS IS DELIBERATELY ABSENT. There is no seller entity in this product:
 * "seller" exists only as a value of the user role enum and as a report/review
 * category. There is no seller table, no seller profile, no seller directory and
 * no endpoint to search one, so the tab could only be filled with invented
 * sellers or wired to a dead route. Both are worse than its absence — the same
 * reasoning that keeps Bookmarks and Recent reads out of the profile panel.
 * Restore it here the moment a real seller surface exists.
 *
 * Real links, not client state: each tab is a distinct set of server-rendered
 * results, so they are `<Link>`s that carry the query across. That keeps them
 * shareable, back-button correct, and working without JavaScript.
 */

export type { SearchTab };

const TABS: { key: SearchTab; label: string }[] = [
  { key: "reviews", label: "Reviews" },
  { key: "questions", label: "Questions" },
];

export function SearchTabs({
  active,
  q,
  category,
  from,
}: {
  active: SearchTab;
  q?: string;
  category?: string;
  from?: string;
}) {
  const href = (tab: SearchTab) => searchTabHref(tab, { q, category, from });

  return (
    <nav
      aria-label="Search results type"
      className="mt-5 border-b border-[var(--line-hairline-10)]"
    >
      <ul className="flex gap-6">
        {TABS.map(({ key, label }) => {
          const current = key === active;
          return (
            <li key={key}>
              <Link
                href={href(key)}
                // `aria-current="page"` rather than a role=tab widget: these
                // navigate to real URLs, so they are links that happen to look
                // like tabs. Announcing them as a tablist would promise
                // arrow-key switching that no longer applies once each tab is
                // its own document.
                aria-current={current ? "page" : undefined}
                className={[
                  "-mb-px inline-flex border-b-2 pb-2.5 text-[14px] no-underline transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
                  "focus-visible:outline-[var(--accent-primary)]",
                  current
                    ? "border-[var(--accent-primary)] font-semibold text-[var(--accent-primary)]"
                    : "border-transparent text-[var(--text-primary)] hover:text-[var(--accent-primary)]",
                ].join(" ")}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default SearchTabs;
