import type { SellerSummary } from "@/lib/sellers";

import { percent } from "./seller-model";

/**
 * FR-4's four seller dimensions, as buyers answered them.
 *
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY. "Seller Page -
 * Review.png" draws stars alone, but FR-4 rates a store on ad accuracy, order
 * completeness, customer service and packaging, and the public page is where a
 * buyer reads them. They sit under the rating card in the frame's type: 12px
 * Light labels over 16px SemiBold values.
 * Omitted, not zeroed, for a store nobody has rated.
 */
export function SellerFigures({ summary }: { summary: SellerSummary }) {
  if (summary.review_count === 0) return null;

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
    <dl
      aria-label="What buyers said"
      className="grid grid-cols-2 gap-x-4 gap-y-3 px-2 text-[var(--text-primary)] sm:grid-cols-3"
    >
      {figures.map((figure) =>
        figure.value === null ? null : (
          <div key={figure.label}>
            <dt className="text-[12px] font-light leading-[18px]">{figure.label}</dt>
            <dd className="text-[16px] font-semibold leading-6">{figure.value}</dd>
          </div>
        ),
      )}
    </dl>
  );
}

export default SellerFigures;
