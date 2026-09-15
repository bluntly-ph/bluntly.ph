"use client";

import { useState } from "react";
import { ArrowsDownUp } from "@phosphor-icons/react";

import { Radio, Section, Sheet } from "@/components/search/SearchFilterBar";

import { type CommentSort, type DateOrder, type RatingOrder } from "./comment-sort-model";

/**
 * The "Sort comments by" sheet, drawn as Figma "Sort" (1591:5408) — the same
 * sheet the search results use, so the two sorts in the product look and
 * behave as one control: a 390px bottom sheet at radius 20 in the page colour,
 * the glyph and 16px Bold title over a hairline, 16px SemiBold section
 * headings over 20px ring radios with 16px Light labels, and "Reset" against a
 * 38px brand pill.
 *
 * Two axes, as the reference draws them: rating first, date breaking its ties.
 * The choice is applied on the pill rather than on every radio, so a reader can
 * change their mind mid-sheet without the thread reordering underneath them.
 *
 * NO FIGMA FRAME for comment sorting itself; the sections are the thread's own
 * two orders.
 */

const RATING: { value: RatingOrder; label: string }[] = [
  { value: "most_helpful", label: "Most helpful" },
  { value: "least_helpful", label: "Least helpful" },
];

const DATE: { value: DateOrder; label: string }[] = [
  { value: "latest", label: "Latest" },
  { value: "oldest", label: "Oldest" },
];

const DEFAULT_SORT: CommentSort = { rating: "most_helpful", date: "latest" };

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
  if (!open) return null;
  // Mounted only while open, so every opening starts from what is applied.
  return <OpenSheet value={value} onApply={onApply} onClose={onClose} />;
}

function OpenSheet({
  value,
  onApply,
  onClose,
}: {
  value: CommentSort;
  onApply: (next: CommentSort) => void;
  onClose: () => void;
}) {
  // Local until committed, so cancelling leaves the thread as it was.
  const [draft, setDraft] = useState<CommentSort>(value);

  return (
    <Sheet
      title="Sort comments"
      icon={<ArrowsDownUp size={20} aria-hidden="true" className="shrink-0" />}
      submitLabel="Sort Comments"
      compact
      onClose={onClose}
      onReset={() => setDraft(DEFAULT_SORT)}
      onSubmit={() => onApply(draft)}
    >
      <Section heading="By rating" compact>
        {RATING.map((o) => (
          <Radio
            key={o.value}
            name="comment-sort-rating"
            value={o.value}
            label={o.label}
            checked={draft.rating === o.value}
            onChange={() => setDraft((d) => ({ ...d, rating: o.value }))}
          />
        ))}
      </Section>
      <Section heading="By date" compact>
        {DATE.map((o) => (
          <Radio
            key={o.value}
            name="comment-sort-date"
            value={o.value}
            label={o.label}
            checked={draft.date === o.value}
            onChange={() => setDraft((d) => ({ ...d, date: o.value }))}
          />
        ))}
      </Section>
    </Sheet>
  );
}

export default SortCommentsSheet;
