import "server-only";

import { apiFetch } from "./api/client";

/**
 * Product-side reads for FR-2: the community price panel and comparison.
 *
 * Both return `null` on failure rather than an empty shape, for the same
 * reason the review reads do: "we could not reach the server" and "there is no
 * data yet" are different answers, and only one of them is the reader's to act
 * on. The price panel has a third state on top of that — *enough* data — which
 * is a property of the data itself, not of the request.
 */

export type PricePanel = {
  product_id: string;
  /** False until ≥3 INDEPENDENT submitters have contributed (FR-2). */
  sufficient: boolean;
  observation_count: number;
  independent_count: number;
  required_independent: number;
  currency: string;
  /** Null whenever `sufficient` is false — the API publishes no prices below the threshold. */
  low: string | null;
  high: string | null;
  median: string | null;
  latest_observed_at: string | null;
  platforms: string[];
};

export type ComparisonEntry = {
  product: {
    id: string;
    canonical_name: string | null;
    category: string | null;
    image_url: string | null;
    review_count: number;
    avg_rating: string | null;
  };
  price: PricePanel;
  review_count: number;
  avg_rating: string | null;
  trust_score: string | null;
  verified_review_count: number;
};

export type Comparison = {
  entries: ComparisonEntry[];
  not_found: string[];
};

export async function getPricePanel(productId: string): Promise<PricePanel | null> {
  try {
    return await apiFetch<PricePanel>(
      `/api/v1/products/${encodeURIComponent(productId)}/prices`,
      { revalidate: 60 },
    );
  } catch {
    return null;
  }
}

/** 2–4 products, side by side. Returns null on transport failure only. */
export async function getComparison(ids: string[]): Promise<Comparison | null> {
  if (ids.length < 2 || ids.length > 4) return null;
  try {
    return await apiFetch<Comparison>(
      `/api/v1/products/compare?ids=${ids.map(encodeURIComponent).join(",")}`,
      { revalidate: 60 },
    );
  } catch {
    return null;
  }
}

/** "₱1,200" — prices arrive as string decimals and must stay that way until display. */
export function peso(value: string | null): string {
  if (value === null) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `₱${n.toLocaleString("en-PH", { maximumFractionDigits: 0 })}`;
}
