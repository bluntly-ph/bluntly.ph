"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowsDownUp, X } from "@phosphor-icons/react";

import {
  type CommentSort,
  type DateOrder,
  type RatingOrder,
} from "./comment-sort-model";
import { Button } from "@/components/ui/Button";

/**
 * The "Sort comments by" sheet.
 *
 * Two axes, matching the reference: a rating group and a date group, each with
 * its own filled radio. Rating is the primary key; date breaks its ties.
 *
 * Portalled to `<body>` for the same reason ProfileNavPanel is — the site header
 * is `backdrop-blur-md`, and a non-`none` backdrop-filter makes an element the
 * containing block for its `fixed` descendants, which would resolve this sheet
 * against the header box instead of the viewport.
 *
 * The choice is applied on "Sort comments" rather than on every radio, as drawn:
 * the button is the commit, so a reader can change their mind mid-sheet without
 * the thread reordering underneath them.
 */

const RATING: { value: RatingOrder; label: string }[] = [
  { value: "most_helpful", label: "Most helpful" },
  { value: "least_helpful", label: "Least helpful" },
];

const DATE: { value: DateOrder; label: string }[] = [
  { value: "latest", label: "Latest" },
  { value: "oldest", label: "Oldest" },
];

export function SortCommentsSheet({
  open,
  value,
  onApply,
  onClose,
}: {
  open: boolean;
  value: CommentSort;
  onApply: (next: CommentSort) => void;
  onClose: () => void;
}) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  // Local until committed, so cancelling leaves the thread as it was.
  const [draft, setDraft] = useState<CommentSort>(value);

  // Derived from `open` rather than synced in an effect: this project lints
  // against setState inside effects, and re-opening should always start from
  // whatever is currently applied.
  const [openedWith, setOpenedWith] = useState<CommentSort | null>(null);
  if (open && openedWith !== value && openedWith === null) {
    setOpenedWith(value);
    setDraft(value);
  }
  if (!open && openedWith !== null) setOpenedWith(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.querySelector<HTMLElement>("input, button")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  const group = <T extends string>(
    legend: string,
    name: string,
    options: { value: T; label: string }[],
    selected: T,
    set: (v: T) => void,
  ) => (
    <fieldset className="mt-4 border-0 p-0">
      <legend className="text-[14px] font-semibold text-[var(--text-primary)]">
        {legend}
      </legend>
      <div className="mt-2 flex flex-col gap-2.5">
        {options.map((o) => (
          <label key={o.value} className="flex cursor-pointer items-center gap-3">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={selected === o.value}
              onChange={() => set(o.value)}
              className="h-5 w-5 shrink-0 cursor-pointer accent-[var(--accent-primary)]"
            />
            <span className="text-[14px] text-[var(--text-primary)]">{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );

  return createPortal(
    <>
      <button
        type="button"
        aria-label="Close sort options"
        onClick={onClose}
        className="fixed inset-0 z-40 cursor-default bg-[rgba(32,32,32,0.32)]"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="fixed inset-x-0 bottom-0 z-50 mx-auto w-full max-w-[26rem] rounded-t-[var(--radius-lg)] bg-[var(--surface-app)] p-5 shadow-[var(--shadow-sheet)] sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[var(--radius-lg)]"
      >
        <div className="flex items-center gap-2">
          <ArrowsDownUp size={20} weight="bold" className="text-[var(--text-primary)]" />
          <h2 id={titleId} className="flex-1 text-[16px] font-bold text-[var(--text-primary)]">
            Sort comments by
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sort options"
            className="grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <X size={18} />
          </button>
        </div>

        <hr className="mt-4 border-[var(--line-hairline-10)]" />

        {group("By rating:", "comment-sort-rating", RATING, draft.rating, (rating) =>
          setDraft((d) => ({ ...d, rating })),
        )}
        {group("By date:", "comment-sort-date", DATE, draft.date, (date) =>
          setDraft((d) => ({ ...d, date })),
        )}

        <div className="mt-6 flex justify-end">
          <Button type="button" onClick={() => onApply(draft)}>
            Sort comments
          </Button>
        </div>
      </div>
    </>,
    document.body,
  );
}

export default SortCommentsSheet;
