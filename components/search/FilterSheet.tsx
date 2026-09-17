"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Info, X } from "@phosphor-icons/react";

/**
 * The bottom-sheet primitives shared by search's "All filters" / "Sort" sheets
 * (SearchFilterBar) and the review page's comment sort (SortCommentsSheet).
 *
 * WHY THEY LIVE HERE AND NOT IN SearchFilterBar.tsx. They used to, and the
 * review page imported them from there. That module also imports the category
 * list from lib/landing-data, which carries nineteen Phosphor icons and the
 * landing page's sample content — and a client module's imports ship whole.
 * So every review page downloaded the search page's category icons to sort a
 * comment thread: a 67 KB (raw) chunk of icons the page never draws, fetched on
 * every client navigation to a review (production build 95d84c2, 2026-09-17).
 * Kept apart, each route pays only for what it renders.
 */

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

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
