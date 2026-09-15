/**
 * The card naming what is being reviewed, with a way to pick again: Figma
 * "Reviewer Page - Step 1.1" (4435:863) and "Seller Review - Step 2"
 * (4627:9613) draw it identically. 78px white at radius 12 with the card
 * shadow; "Currently reviewing" in 12px Regular trust blue 16px down and 31px
 * in, the name 10px under it 20px in, in 16px Regular at 0.8px tracking, and
 * "Change" in 14px Regular at 30% ink against the right.
 *
 * "Question Page - Step 2" (4695:14599) draws the same card as "Product in
 * question:", with the label lined up with the name instead of 11px further in.
 */
export function CurrentlyReviewingCard({
  name,
  onChange,
  label = "Currently reviewing",
  labelInset = true,
}: {
  name: string | null;
  onChange: () => void;
  label?: string;
  /** The reviewing frames set the label 11px in from the name; the question frame does not. */
  labelInset?: boolean;
}) {
  return (
    <div className="relative h-[78px] rounded-[12px] bg-[var(--surface-card)] pl-5 pr-[84px] shadow-[var(--shadow-card)]">
      <p className={`pt-4 text-[12px] leading-none text-[var(--accent-trust)] ${labelInset ? "ml-[11px]" : ""}`}>
        {label}
      </p>
      <p className="mt-2.5 truncate text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">
        {name ?? "your product"}
      </p>
      <button
        type="button"
        onClick={onChange}
        className="absolute right-2 top-[29px] cursor-pointer p-3 text-[14px] leading-none text-[rgba(32,32,32,0.3)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
      >
        Change
      </button>
    </div>
  );
}

export default CurrentlyReviewingCard;
