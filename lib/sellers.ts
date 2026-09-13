import "server-only";

import { apiFetch } from "./api/client";
import type { QAAuthor } from "./qa";
import { getSessionToken } from "./session";
import type { SellerPlatform } from "@/components/sellers/seller-model";

export type SellerClaimStatus = "unclaimed" | "pending" | "claimed" | "rejected";

export type Seller = {
  id: string;
  display_name: string;
  platform: SellerPlatform;
  store_url: string | null;
  claim_status: SellerClaimStatus;
  /** Visible reviews only; a removed one no longer counts. */
  review_count: number;
  /** Null until someone has rated the store. */
  overall_average: number | null;
  created_at: string;
};

export type SellerSummary = {
  review_count: number;
  accuracy_rate: number | null;
  order_completeness_rate: number | null;
  recommend_rate: number | null;
  customer_service_average: number | null;
  packaging_quality_average: number | null;
  overall_average: number | null;
  /** "1".."5" -> count. */
  rating_distribution: Record<string, number>;
};

export type SellerDetail = Seller & { summary: SellerSummary };

export type SellerReview = {
  id: string;
  seller_id: string;
  product_id: string | null;
  title: string | null;
  accuracy: boolean;
  order_completeness: boolean;
  customer_service: number;
  packaging_quality: number;
  overall_rating: number;
  would_recommend: boolean;
  comment: string | null;
  photo_urls: string[];
  reviewer: QAAuthor | null;
  created_at: string;
};

export type SellerClaim = {
  id: string;
  seller_id: string;
  seller_display_name: string | null;
  status: SellerClaimStatus;
  evidence: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
};

/** Store search for the Sellers tab. Public. Null means unreachable. */
export async function searchSellers(q: string, limit = 24): Promise<Seller[] | null> {
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    const needle = q.trim();
    if (needle) params.set("q", needle);
    return await apiFetch<Seller[]>(`/api/v1/sellers?${params}`, { revalidate: 60 });
  } catch {
    return null;
  }
}

/**
 * One store with its summary. Short-lived cache: a buyer who has just rated
 * the store lands here from the composer, and a minute-old summary would read
 * as if their rating had not counted.
 */
export async function getSeller(id: string): Promise<SellerDetail | null> {
  try {
    return await apiFetch<SellerDetail>(`/api/v1/sellers/${encodeURIComponent(id)}`, {
      revalidate: 5,
    });
  } catch {
    return null;
  }
}

export async function getSellerReviews(id: string, limit = 30): Promise<SellerReview[] | null> {
  try {
    return await apiFetch<SellerReview[]>(
      `/api/v1/sellers/${encodeURIComponent(id)}/reviews?limit=${limit}`,
      { revalidate: 5 },
    );
  } catch {
    return null;
  }
}

/** Moderator only. Per-user data, so never cached. */
export async function getPendingSellerClaims(): Promise<SellerClaim[] | null> {
  try {
    return await apiFetch<SellerClaim[]>("/api/v1/admin/seller-claims?limit=100", {
      token: await getSessionToken(),
    });
  } catch {
    return null;
  }
}
