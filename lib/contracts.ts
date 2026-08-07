import "server-only";

import { apiFetch } from "./api/client";
import { getReviewFull } from "./reviews";
import { getSessionToken } from "./session";

/**
 * Revenue-share contracts (M3 slice 10). One contract per monetized review,
 * created automatically when a moderator first attaches an affiliate link —
 * there is no create endpoint and nothing for the reviewer to sign up for.
 *
 * The economic effect is at reconciliation: the reviewer earns their tier's
 * share while the contract is `active`, and nothing once it is `expired` or
 * `bought_out`. The Honesty Fund's cut is unaffected either way.
 */

export type Contract = {
  id: string;
  review_id: string;
  reviewer_id: string | null;
  status: "active" | "expired" | "bought_out";
  started_at: string;
  term_months: number;
  expires_at: string;
  auto_renew: boolean;
  renewal_count: number;
  buyout_offer_amount: string | null;
  buyout_offered_at: string | null;
  buyout_accepted_at: string | null;
  buyout_rejected_at: string | null;
  created_at: string;
};

/** A contract with the title of the review it covers, for a readable list. */
export type ContractWithReview = Contract & { reviewTitle: string | null };

export async function getContracts(): Promise<ContractWithReview[]> {
  const token = await getSessionToken();
  if (!token) return [];

  let contracts: Contract[];
  try {
    contracts = await apiFetch<Contract[]>("/api/v1/contracts?limit=50", { token });
  } catch {
    return [];
  }

  // Titles come from the public review endpoint, one per contract. A reviewer
  // has a handful of monetized reviews, so the fan-out is small and bounded by
  // the API's own limit of 50; a failed lookup degrades to "no title", never to
  // a failed page.
  return Promise.all(
    contracts.map(async (c) => ({
      ...c,
      reviewTitle: await getReviewFull(c.review_id)
        .then((r) => r?.review.title ?? null)
        .catch(() => null),
    })),
  );
}

/** A buyout the reviewer still has to answer. */
export function hasOpenBuyout(c: Contract): boolean {
  return (
    c.buyout_offer_amount !== null &&
    c.buyout_offered_at !== null &&
    c.buyout_accepted_at === null &&
    c.buyout_rejected_at === null &&
    c.status === "active"
  );
}

/** Whole days until expiry; negative once past. */
export function daysUntil(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}
