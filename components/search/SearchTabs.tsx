import Link from "next/link";

import { searchTabHref, type ReviewSort, type SearchTab } from "./search-tabs-model";

/**
 * The Reviews / Questions / Sellers tab strip on /search.
 *
 * Sellers was held back while the product had no seller entity, because the
 * tab could only have been filled with invented stores. The completion
 * contract reinstated sellers (migration 0042, GET /sellers), so all three are
 * drawn and each is backed by a real search.
 *
 * Phone, from the three "Mobile Search Page" frames (3481:1776, 3481:1894,
 * 3954:650), read 2026-09-14: 12px Poppins Regular labels at x16 / x96 / x188,
 * 22px under the field, the current tab in --accent-primary with no underline,
 * and a full-bleed 1px rule 13px under the labels, drawn at #202020 with 30%
 * opacity on a 30% stroke (--line-hairline-10). From `md` up there is no frame,
 * so the underlined desktop strip stays.
 *
 * Real links, not client state: each tab is a distinct set of server-rendered
 * results, so they are `<Link>`s that carry the query across. That keeps them
 * shareable, back-button correct, and working without JavaScript.
 */

export type { SearchTab };

const TABS: { key: SearchTab; label: string }[] = [
  { key: "reviews", label: "Reviews" },
  { key: "questions", label: "Questions" },
  { key: "sellers", label: "Sellers" },
];

export function SearchTabs({
  active,
  q,
  category,
  sort,
  from,
}: {
  active: SearchTab;
  q?: string;
  category?: string;
  sort?: ReviewSort;
  from?: string;
}) {
  const href = (tab: SearchTab) => searchTabHref(tab, { q, category, sort, from });

  return (
    <nav
      aria-label="Search results type"
      className="-mx-4 mt-[22px] border-b border-[var(--line-hairline-10)] px-4 md:mx-0 md:mt-5 md:px-0"
    >
      <ul className="flex gap-8 md:gap-6">
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
                  // `flex`, not `inline-flex`: an inline box sits on the li's
                  // 24px line box and dropped the 12px labels 7px below the
                  // frame's y.
                  "flex pb-[13px] text-[12px] leading-none no-underline transition-colors",
                  "md:-mb-px md:border-b-2 md:pb-2.5 md:text-[14px] md:leading-5",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
                  "focus-visible:outline-[var(--accent-primary)]",
                  current
                    ? "text-[var(--accent-primary)] md:border-[var(--accent-primary)] md:font-semibold"
                    : "text-[var(--text-primary)] hover:text-[var(--accent-primary)] md:border-transparent",
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
