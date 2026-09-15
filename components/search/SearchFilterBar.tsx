"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ArrowsDownUp, Info, Sliders, X } from "@phosphor-icons/react";

import { CATEGORIES } from "@/lib/landing-data";

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

/**
 * The bottom sheet both pills open. Portalled to `<body>` for the reason
 * ProfileNavPanel is: a non-`none` backdrop-filter on an ancestor becomes the
 * containing block for `fixed` descendants. From `md` up, where no frame draws
 * it, the same 390px panel is centred as a dialog.
 */
export function Sheet({
  title,
  icon,
  submitLabel,
  compact = false,
  onClose,
  onReset,
  onSubmit,
  children,
}: {
  title: string;
  icon: ReactNode;
  submitLabel: string;
  /** The Sort frame sets its rule 2px higher and its sections tighter. */
  compact?: boolean;
  onClose: () => void;
  onReset: () => void;
  onSubmit: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const panel = panelRef.current;
    (panel?.querySelector<HTMLElement>("input:checked") ?? panel?.querySelector<HTMLElement>("input, button"))?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return createPortal(
    <>
      {/* Pointer-only: keyboard users close with Escape or the X. */}
      <div aria-hidden="true" onClick={onClose} className="fixed inset-0 z-40 bg-[var(--overlay-scrim-25)]" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[85dvh] w-full max-w-[390px] flex-col rounded-t-[20px] bg-[var(--surface-app)] text-[var(--text-primary)] shadow-[var(--shadow-sheet)] md:bottom-auto md:top-1/2 md:-translate-y-1/2 md:rounded-[20px]"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          {/* Top-aligned, as drawn: the title sits 2px under the glyph's top,
              not on its centre. */}
          <div className="flex items-start gap-2 px-6 pt-6">
            {icon}
            <h2 id={titleId} className="mt-0.5 flex-1 text-[16px] font-bold leading-none">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={`Close ${title.toLowerCase()}`}
              className={`-my-2 -mr-2 grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-full hover:bg-[var(--line-hairline-10)] ${FOCUS}`}
            >
              <X size={28} aria-hidden="true" />
            </button>
          </div>
          <hr className={`mx-6 border-0 border-t border-[var(--line-hairline-30)] ${compact ? "mt-[22px]" : "mt-6"}`} />

          <div className={`flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pt-[15px] ${compact ? "gap-[26px]" : "gap-7"}`}>
            {children}
          </div>

          <div className={`flex items-center justify-between px-6 pb-8 ${compact ? "pt-[38px]" : "pt-[43px]"}`}>
            <button
              type="button"
              onClick={onReset}
              className={`cursor-pointer text-[16px] leading-none tracking-[0.8px] ${FOCUS}`}
            >
              Reset
            </button>
            <button
              type="submit"
              className={`h-[38px] cursor-pointer rounded-[20px] bg-[var(--accent-primary)] px-2 text-[16px] leading-none tracking-[0.8px] text-[var(--text-on-brand)] hover:bg-[var(--accent-primary-strong)] ${FOCUS}`}
            >
              {submitLabel}
            </button>
          </div>
        </form>
      </div>
    </>,
    document.body,
  );
}

export function Section({
  heading,
  info,
  compact = false,
  children,
}: {
  heading: string;
  /** The All filters frame puts an Info glyph beside each heading. */
  info?: string;
  compact?: boolean;
  children: ReactNode;
}) {
  const [showInfo, setShowInfo] = useState(false);
  const headingId = useId();
  const infoId = useId();

  return (
    <div role="group" aria-labelledby={headingId} className="shrink-0">
      <div className="flex items-center gap-2">
        <h3 id={headingId} className="text-[16px] font-semibold leading-none">
          {heading}
        </h3>
        {info ? (
          <button
            type="button"
            aria-label={`About ${heading.toLowerCase()}`}
            aria-expanded={showInfo}
            aria-controls={showInfo ? infoId : undefined}
            onClick={() => setShowInfo((v) => !v)}
            className={`-m-0.5 grid h-6 w-6 cursor-pointer place-items-center rounded-full text-[var(--line-hairline-30)] hover:text-[var(--text-secondary)] ${FOCUS}`}
          >
            <Info size={20} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {info && showInfo ? (
        <p id={infoId} className="mt-2 text-[12px] font-light leading-[18px] text-[var(--text-secondary)]">
          {info}
        </p>
      ) : null}
      {/* Options start 40px under the heading row's top in both frames; the
          Info glyph makes that row 20px tall, a bare heading 16px. */}
      <div className={`flex flex-col ${info ? "mt-5" : "mt-6"} ${compact ? "gap-[14px]" : "gap-4"}`}>{children}</div>
    </div>
  );
}

export function Radio({
  name,
  value,
  label,
  checked,
  onChange,
}: {
  name: string;
  value: string;
  label: string;
  checked: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="relative flex cursor-pointer items-center gap-3">
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
        className="peer sr-only"
      />
      <span
        aria-hidden="true"
        className="h-5 w-5 shrink-0 rounded-full border border-[var(--line-hairline-30)] peer-checked:bg-[var(--accent-primary)] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent-primary)]"
      />
      <span className="text-[16px] font-light leading-none">{label}</span>
    </label>
  );
}

export default SearchFilterBar;
