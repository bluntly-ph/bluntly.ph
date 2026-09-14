import type { SellerSummary } from "@/lib/sellers";

import { StarRow } from "./SellerIdentity";
import { distributionBars, ratingWord } from "./seller-model";

/**
 * The seller page's rating card: Figma "Group 670" (4298:2359) in "Seller Page -
 * Review", read 2026-09-14.
 *
 * 358x171 at radius 16 on the page's own grey with a 1px outline at 30% ink and
 * no shadow; 24px in. The average in 20px SemiBold, 10px to its word in 12px
 * Light, 10px to 20px stars, 4px to the count in 10px Light. Beside them five
 * 136x12 bars at radius 10 on a 27px pitch, their "5 star" labels in 10px
 * Light, 34px clear of the right edge. No counts beside the bars — the frame
 * draws none — so each bar carries its count for screen readers only.
 *
 * The FR-4 figures render beneath the card as `SellerFigures`: they are
 * required, and the frame's card has no room for them.
 */

/** The frame's bar colours, top to bottom. Only the first has a token. */
export const STAR_BAR_COLOUR: Record<number, string> = {
  5: "var(--accent-success)",
  4: "#9ac34c",
  3: "#e5b50a",
  2: "#e85a22",
  1: "#ff4500",
};

export function SellerRatingSummary({ summary }: { summary: SellerSummary }) {
  const bars = distributionBars(summary.rating_distribution);
  const average = summary.overall_average;
  const count = summary.review_count;

  return (
    <section
      aria-label="Seller rating"
      className="rounded-[16px] border border-[var(--line-hairline-30)] bg-[var(--surface-app)] py-6 pl-6 pr-[33px] text-[var(--text-primary)]"
    >
      {/* Top-aligned: the average starts on the card's inner top edge, level
          with the first bar, not centred against the bar stack. */}
      {/* 10px to the labels puts them at x167 and the bars at x204, 136 wide. */}
      <div className="flex items-start gap-[10px]">
        <div className="w-[116px] shrink-0">
          {average === null ? (
            <p className="text-[16px] font-medium leading-5">No ratings yet</p>
          ) : (
            <>
              <p className="text-[20px] font-semibold leading-none">{average.toFixed(1)}</p>
              <p className="mt-2.5 text-[12px] font-light leading-none">{ratingWord(average)}</p>
            </>
          )}
          <StarRow value={average} size={20} gap={0} className="mt-2.5" />
          <p className="mt-1 text-[10px] font-light leading-none">
            {count} {count === 1 ? "review" : "reviews"}
          </p>
        </div>

        <ul className="mt-0.5 flex flex-1 flex-col gap-[15px]">
          {bars.map((bar) => (
            <li key={bar.star} className="flex items-center gap-2">
              <span className="w-[29px] shrink-0 whitespace-nowrap text-[10px] font-light leading-3">
                {bar.star} star
              </span>
              <span className="h-3 flex-1 overflow-hidden rounded-[10px] bg-[var(--base-gray-200)]">
                <span
                  className="block h-full rounded-[10px]"
                  style={{ width: `${bar.share * 100}%`, background: STAR_BAR_COLOUR[bar.star] }}
                />
              </span>
              <span className="sr-only">
                {bar.count} {bar.count === 1 ? "review" : "reviews"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default SellerRatingSummary;
