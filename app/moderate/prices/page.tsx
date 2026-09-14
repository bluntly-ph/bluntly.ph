import type { Metadata } from "next";

import { PriceObservationDecision } from "@/components/admin/PriceObservationDecision";
import { getPendingPriceObservations } from "@/lib/products";

export const metadata: Metadata = { title: "Prices — bluntly admin" };

const PLATFORM: Record<string, string> = {
  shopee: "Shopee",
  lazada: "Lazada",
  amazon: "Amazon",
  other: "Other",
};

function exactPeso(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : value;
}

/**
 * Community prices waiting for a moderator (FR-2).
 *
 * Every observation starts pending and the public price panel is built from
 * approved ones alone, so nothing a buyer reports reaches a product page
 * without passing here. Exact centavos, not the panel's rounded pesos: a
 * moderator is checking the number itself.
 */
export default async function PricesAdminPage() {
  const rows = await getPendingPriceObservations();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 pb-3">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Price observations</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          {rows
            ? `${rows.length} price${rows.length === 1 ? "" : "s"} waiting, oldest first.`
            : "Unable to load price observations right now."}{" "}
          Approve a price that is plausible for the product and marketplace; reject a typo, a
          listing price someone did not pay, or a joke. A product&rsquo;s price range appears once
          three different buyers have an approved price. You cannot decide a price you reported.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        <table className="w-full min-w-[52rem] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Price</th>
              <th className="px-4 py-3 font-medium">Where</th>
              <th className="px-4 py-3 font-medium">Paid on</th>
              <th className="px-4 py-3 font-medium">Reported by</th>
              <th className="px-4 py-3 font-medium">Decision</th>
            </tr>
          </thead>
          <tbody>
            {!rows || rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                  {rows ? "No prices waiting." : "Unable to load price observations."}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border-subtle)] align-top text-[13px]">
                  <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                    {row.product_name ?? "Unnamed product"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 [font-variant-numeric:tabular-nums] font-semibold text-[var(--text-primary)]">
                    {exactPeso(row.price)}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {PLATFORM[row.platform] ?? row.platform}
                    {row.variant ? <span className="block text-[12px]">{row.variant}</span> : null}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[12px] text-[var(--text-muted)]">
                    {new Date(row.observed_at).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {row.submitter_username ?? "Former member"}
                    <span className="block text-[12px] text-[var(--text-muted)]">
                      {row.source === "review" ? "From a review" : "Price report"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <PriceObservationDecision
                      observationId={row.id}
                      label={`${exactPeso(row.price)} for ${row.product_name ?? "this product"}`}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
