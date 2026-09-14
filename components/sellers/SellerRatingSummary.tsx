import type { SellerSummary } from "@/lib/sellers";

import { StarRow } from "./SellerIdentity";
import { distributionBars, ratingWord } from "./seller-model";

/**
 * The seller page's rating card, measured from "Seller Page - Review.png":
 * a 1px #b3b3b3 border at radius 12 on the page's own grey with the card
 * shadow; the average at 20px, its word at 12px, 20px stars and the count at
 * 10px in a 116px column; then five 136px-wide, 12px bars on a 27px pitch with
 * their "5 star" labels at 11px. No counts beside the bars — the frame draws
 * none — so each bar carries its count for screen readers only.
 *
 * The FR-4 figures that used to sit inside this card now render beneath it as
 * `SellerFigures`: they are required, and the frame's card has no room for them.
 */

/** The frame's bar colours, top to bottom. Only the first has a token. */
export const STAR_BAR_COLOUR: Record<number, string> = {
  5: "var(--accent-success)",
  4: "#9ac34c",
  3: "#e5b50a",
  2: "#e85a22",
  1: "#ff4500",
};

const FACE = "font-[family-name:var(--font-system)]";

export function SellerRatingSummary({ summary }: { summary: SellerSummary }) {
  const bars = distributionBars(summary.rating_distribution);
  const average = summary.overall_average;
  const count = summary.review_count;

  return (
    <section
      aria-label="Seller rating"
      className="rounded-[var(--radius-sm)] border border-[#b3b3b3] bg-[var(--surface-app)] py-6 pl-6 pr-[33px] shadow-[var(--shadow-card)]"
    >
      {/* Top-aligned: the frame's average starts on the card's inner top edge,
          level with the first bar, not centred against the bar stack. */}
      <div className="flex items-start gap-3">
        <div className="w-[116px] shrink-0">
          {average === null ? (
            <p className="text-[15px] font-medium leading-5 text-[var(--text-primary)]">No ratings yet</p>
          ) : (
            <>
              <p className="text-[20px] font-semibold leading-5 text-[var(--text-primary)]">
                {average.toFixed(1)}
              </p>
              <p className={`mt-2 ${FACE} text-[12px] leading-4 text-[var(--text-primary)]`}>
                {ratingWord(average)}
              </p>
            </>
          )}
          <StarRow value={average} size={20} className="mt-[7px]" />
          <p className={`mt-[3px] ${FACE} text-[10px] leading-[14px] text-[var(--text-primary)]`}>
            {count} {count === 1 ? "review" : "reviews"}
          </p>
        </div>

        <ul className="mt-px flex flex-1 flex-col gap-[15px]">
          {bars.map((bar) => (
            <li key={bar.star} className="flex items-center gap-3">
              <span className={`w-[23px] shrink-0 whitespace-nowrap ${FACE} text-[11px] leading-3 text-[var(--text-primary)]`}>
                {bar.star} star
              </span>
              <span className="h-3 flex-1 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                <span
                  className="block h-full rounded-full"
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
