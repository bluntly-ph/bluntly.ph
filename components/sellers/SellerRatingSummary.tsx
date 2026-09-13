import type { SellerSummary } from "@/lib/sellers";

import { StarRow } from "./SellerIdentity";
import { distributionBars, percent, ratingWord } from "./seller-model";

/**
 * The seller page's rating card: the average, its word, the stars, and the
 * five-to-one breakdown, as "Seller Page - Review.png" draws it.
 *
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY. The frame shows the
 * stars alone. FR-4 rates a seller on four dimensions — ad accuracy, order
 * completeness, customer service, packaging — and the public summary is where
 * a buyer reads them, so they sit under the breakdown in the card's own type.
 * They are omitted, not zeroed, for a store nobody has rated.
 */

const BAR_COLOUR: Record<number, string> = {
  5: "var(--accent-success)",
  4: "color-mix(in srgb, var(--accent-success) 60%, var(--accent-star))",
  3: "var(--accent-star)",
  2: "var(--accent-primary)",
  1: "var(--accent-danger)",
};

export function SellerRatingSummary({ summary }: { summary: SellerSummary }) {
  const bars = distributionBars(summary.rating_distribution);
  const average = summary.overall_average;
  const count = summary.review_count;

  const figures: { label: string; value: string | null }[] = [
    { label: "Matched the listing", value: percent(summary.accuracy_rate) },
    { label: "Arrived complete", value: percent(summary.order_completeness_rate) },
    { label: "Would recommend", value: percent(summary.recommend_rate) },
    {
      label: "Customer service",
      value:
        summary.customer_service_average === null
          ? null
          : `${summary.customer_service_average.toFixed(1)} / 5`,
    },
    {
      label: "Packaging",
      value:
        summary.packaging_quality_average === null
          ? null
          : `${summary.packaging_quality_average.toFixed(1)} / 5`,
    },
  ];

  return (
    <section
      aria-label="Seller rating"
      className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
    >
      <div className="flex gap-6">
        <div className="shrink-0">
          {average === null ? (
            <p className="text-[15px] font-medium text-[var(--text-primary)]">No ratings yet</p>
          ) : (
            <>
              <p className="text-[28px] font-semibold leading-none text-[var(--text-primary)]">
                {average.toFixed(1)}
              </p>
              <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{ratingWord(average)}</p>
            </>
          )}
          <StarRow value={average} size={20} className="mt-2" />
          <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
            {count} {count === 1 ? "review" : "reviews"}
          </p>
        </div>

        <ul className="flex flex-1 flex-col justify-center gap-1.5">
          {bars.map((bar) => (
            <li key={bar.star} className="flex items-center gap-3 text-[12px]">
              <span className="w-11 shrink-0 text-[var(--text-secondary)]">{bar.star} star</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                <span
                  className="block h-full rounded-full"
                  style={{ width: `${bar.share * 100}%`, background: BAR_COLOUR[bar.star] }}
                />
              </span>
              <span className="w-6 shrink-0 text-right tabular-nums text-[var(--text-secondary)]">
                {bar.count}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {count > 0 ? (
        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[var(--line-hairline-10)] pt-4 sm:grid-cols-3">
          {figures.map((figure) =>
            figure.value === null ? null : (
              <div key={figure.label}>
                <dt className="text-[12px] text-[var(--text-secondary)]">{figure.label}</dt>
                <dd className="text-[15px] font-semibold text-[var(--text-primary)]">
                  {figure.value}
                </dd>
              </div>
            ),
          )}
        </dl>
      ) : null}
    </section>
  );
}

export default SellerRatingSummary;
