import type { Metadata } from "next";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

export const metadata: Metadata = { title: "Products — bluntly admin" };

type AdminProduct = {
  id: string;
  canonical_name: string | null;
  brand?: string | null;
  category?: string | null;
  review_count?: number;
};

/**
 * The product catalogue, read-only.
 *
 * Products are created by the reviews written about them rather than entered
 * by a moderator, so this screen is a catalogue view: what exists, and how much
 * has been written about each. `include_low_trust` is on because a moderator
 * should see everything, including what the public listing filters out.
 */
export default async function ProductsPage() {
  const products = await apiFetch<AdminProduct[]>(
    "/api/v1/products?limit=100&include_low_trust=true",
  ).catch(() => null);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 pb-3">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Products</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          {products
            ? `${products.length} in the catalogue, including entries the public listing filters out.`
            : "Unable to load the catalogue right now."}{" "}
          Products are created by the reviews written about them, so there is nothing to
          add here by hand.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        <table className="w-full min-w-[34rem] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Category</th>
              <th className="px-4 py-3 font-medium">Reviews</th>
            </tr>
          </thead>
          <tbody>
            {!products || products.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                  {products ? "The catalogue is empty." : "Unable to load the catalogue."}
                </td>
              </tr>
            ) : (
              products.map((p) => (
                <tr key={p.id} className="border-t border-[var(--border-subtle)] text-[13px]">
                  <td className="px-4 py-2.5">
                    {/* There is no /products/[id] route in this build, and
                        linking to one made Next prefetch a 404 for every row.
                        Search is the real destination: it finds the reviews
                        written about the product, which is what a moderator is
                        actually looking for. */}
                    <Link
                      href={`/search?q=${encodeURIComponent(p.canonical_name ?? "")}`}
                      className="font-medium text-[var(--text-primary)] underline hover:text-[var(--accent-primary)]"
                    >
                      {p.canonical_name ?? "Unnamed product"}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                    {p.category ?? <span className="text-[var(--text-muted)]">&mdash;</span>}
                  </td>
                  <td className="px-4 py-2.5 [font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                    {p.review_count ?? 0}
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
