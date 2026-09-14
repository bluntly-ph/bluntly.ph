import Link from "next/link";

import { searchTabHref, type SearchTab } from "./search-tabs-model";

/**
 * The Reviews / Questions / Sellers tab strip on /search.
 *
 * Sellers was held back while the product had no seller entity, because the
 * tab could only have been filled with invented stores. The completion
 * contract reinstated sellers (migration 0042, GET /sellers), so all three are
 * drawn and each is backed by a real search.
 *
 * Phone, measured from the three "Mobile Search Page" frames: 13px regular
 * labels about 32px apart, the current tab in brand orange with no underline,
 * and a 2px full-bleed rule 20px below the field's bottom edge plus the label
 * line. From `md` up there is no frame, so the underlined desktop strip stays.
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
      className="-mx-4 mt-[15px] border-b-2 border-[var(--base-gray-150)] px-4 md:mx-0 md:mt-5 md:border-b md:border-[var(--line-hairline-10)] md:px-0"
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
                  // Phone labels are set in the frames' grotesque, not Poppins:
                  // "Reviews" measures 46px wide with a 9px cap height, which is
                  // 13px Arial, where 13px Poppins renders it 50px wide.
                  "inline-flex pb-[9px] font-[family-name:var(--font-system)] text-[13px] leading-5 no-underline transition-colors",
                  "md:-mb-px md:border-b-2 md:pb-2.5 md:font-[family-name:inherit] md:text-[14px]",
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
