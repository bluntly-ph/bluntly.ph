"use client";

import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { ArrowsDownUp, Sliders } from "@phosphor-icons/react";

import { CATEGORIES } from "@/lib/landing-data";

import { Radio, Section, Sheet } from "./FilterSheet";

import {
  clearCategoryHref,
  searchTabHref,
  type ReviewSort,
} from "./search-tabs-model";

/**
 * The "All filters" and "Sort" pills under the result tabs, and the sheets they
 * open. Figma, read 2026-09-14: "Chip/Action" (7166:4933) placed in "Mobile
 * Search Page for Buyers" (3481:1776); the sheets "All filters" (1587:4658) and
 * "Sort" (1591:5408).
 *
 * Pills: 32px tall, 12px sides, a 16px glyph 4px before 12px Poppins Regular,
 * radius 16, a 1px ink outline — the brand outline and text once the reader
 * has applied one. 12px apart, 12px under the tab rule. An applied filter
 * follows a 26px hairline as a filled brand chip, as the frame draws "80 - 100"
 * and "All time"; tapping it reopens the sheet.
 *
 * Sheets: --surface-app with a 20px top radius; a 28px glyph and 16px Bold
 * title 24px in, the close X 24px from the right; a 342px rule at 30% ink;
 * 16px SemiBold section headings (with a 20px Info glyph in All filters) over
 * 20px radios — a 30% ink ring, filled brand when chosen — beside 16px Light
 * labels; then "Reset" and a 38px brand button, both 16px Regular at 0.8px.
 *
 * The choice commits on the button, as drawn, so a reader can change their
 * mind mid-sheet without the results reloading underneath them.
 *
 * INTENTIONAL PRODUCT DIFFERENCES — only what the feed can actually do is
 * offered, because a radio that changes nothing is a dead control:
 *  - All filters carries Category, the one filter GET /reviews/feed serves. The
 *    frame's Review score (Hidden Gems, Controversial, Trending), Trust rating,
 *    Budget and Time sections have no parameter behind them.
 *  - Sort carries the feed's two orders: "Most Helpful", under the All filters
 *    frame's "Review score:" heading where the file names that order, and
 *    "Latest" under "By date:". Reviewer credibility and Oldest are not served.
 *  - Questions and sellers serve no filter or order, so the pills are drawn on
 *    the Reviews tab only.
 */

type SheetKind = "filters" | "sort";

const FILTER_CATEGORIES = CATEGORIES.filter((c) => c.slug !== "trending");

const SORT_SECTIONS: { heading: string; value: ReviewSort; label: string }[] = [
  { heading: "Review score:", value: "wilson", label: "Most Helpful" },
  { heading: "By date:", value: "newest", label: "Latest" },
];

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

// 11px sides: Figma strokes inside the frame, so its 12px padding includes the
// 1px outline ("Sort" measures 68px there).
const PILL =
  "inline-flex h-8 shrink-0 cursor-pointer items-center gap-1 whitespace-nowrap rounded-[var(--radius-md)] px-[11px] text-[12px] leading-none";

export function SearchFilterBar({
  q,
  category,
  sort,
  from,
}: {
  q?: string;
  category?: string;
  sort: ReviewSort;
  from?: string;
}) {
  const router = useRouter();
  const [sheet, setSheet] = useState<SheetKind | null>(null);
  const [draftCategory, setDraftCategory] = useState("");
  const [draftSort, setDraftSort] = useState<ReviewSort>(sort);
  const trigger = useRef<HTMLButtonElement | null>(null);

  const activeCategory = FILTER_CATEGORIES.find((c) => c.slug === category);
  const CategoryIcon = activeCategory?.icon;

  const open = (kind: SheetKind, from: HTMLButtonElement) => {
    trigger.current = from;
    // Every opening starts from what is applied, so a cancelled change is gone.
    setDraftCategory(activeCategory?.slug ?? "");
    setDraftSort(sort);
    setSheet(kind);
  };

  // Stable, so the sheet's key and scroll-lock effect runs once per opening.
  const close = useCallback(() => {
    setSheet(null);
    trigger.current?.focus();
  }, []);

  const go = (href: string) => {
    setSheet(null);
    router.push(href);
  };

  const outline = (active: boolean) =>
    `${PILL} border ${
      active
        ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
        : "border-[var(--text-primary)] text-[var(--text-primary)]"
    } ${FOCUS}`;

  return (
    <>
      {/* 2px of vertical padding, taken back out of the margins, so the focus
          ring is not clipped by the scroller while the pills stay on the
          frame's y — 12px under the tab rule. */}
      <div className="-mx-4 -mb-0.5 mt-2.5 overflow-x-auto px-4 py-0.5 [scrollbar-width:none] md:mx-0 md:mt-[18px] md:px-0">
        <div className="flex w-max items-center gap-3">
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={sheet === "filters"}
            onClick={(e) => open("filters", e.currentTarget)}
            className={outline(Boolean(activeCategory))}
          >
            <Sliders size={16} aria-hidden="true" className="rotate-90" />
            All filters
          </button>
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={sheet === "sort"}
            onClick={(e) => open("sort", e.currentTarget)}
            className={outline(sort !== "wilson")}
          >
            <ArrowsDownUp size={16} aria-hidden="true" />
            Sort
          </button>
          {activeCategory && CategoryIcon ? (
            <>
              <span aria-hidden="true" className="h-[26px] w-px shrink-0 bg-[var(--line-hairline-30)]" />
              <button
                type="button"
                aria-haspopup="dialog"
                aria-label={`Category: ${activeCategory.label}. Change filters`}
                onClick={(e) => open("filters", e.currentTarget)}
                className={`${PILL} bg-[var(--accent-primary)] text-[var(--text-on-brand)] ${FOCUS}`}
              >
                <CategoryIcon size={16} aria-hidden="true" />
                {activeCategory.label}
              </button>
            </>
          ) : null}
        </div>
      </div>

      {sheet === "filters" ? (
        <Sheet
          title="All filters"
          icon={<Sliders size={28} aria-hidden="true" className="rotate-90" />}
          submitLabel="Filter Reviews"
          onClose={close}
          onReset={() => go(clearCategoryHref({ q, sort, from }))}
          onSubmit={() =>
            go(
              draftCategory
                ? searchTabHref("reviews", { q, category: draftCategory, sort, from })
                : clearCategoryHref({ q, sort, from }),
            )
          }
        >
          <Section heading="Category" info="Shows only reviews of products in the category you pick.">
            <Radio
              name="category"
              value=""
              label="All categories"
              checked={draftCategory === ""}
              onChange={setDraftCategory}
            />
            {FILTER_CATEGORIES.map((c) => (
              <Radio
                key={c.slug}
                name="category"
                value={c.slug}
                label={c.label}
                checked={draftCategory === c.slug}
                onChange={setDraftCategory}
              />
            ))}
          </Section>
        </Sheet>
      ) : null}

      {sheet === "sort" ? (
        <Sheet
          title="Sort"
          icon={<ArrowsDownUp size={28} aria-hidden="true" />}
          submitLabel="Sort Reviews"
          compact
          onClose={close}
          onReset={() => go(searchTabHref("reviews", { q, category, from }))}
          onSubmit={() => go(searchTabHref("reviews", { q, category, sort: draftSort, from }))}
        >
          {SORT_SECTIONS.map((s) => (
            <Section key={s.value} heading={s.heading} compact>
              <Radio
                name="sort"
                value={s.value}
                label={s.label}
                checked={draftSort === s.value}
                onChange={(v) => setDraftSort(v === "newest" ? "newest" : "wilson")}
              />
            </Section>
          ))}
        </Sheet>
      ) : null}
    </>
  );
}

export default SearchFilterBar;
