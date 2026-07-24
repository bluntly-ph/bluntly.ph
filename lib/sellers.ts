import "server-only";

import { apiFetch } from "./api/client";

export type SellerProfile = {
  id: string;
  display_name: string | null;
  seller_trust_score: string | null;
  low_trust: boolean;
  review_count: number;
  accuracy_pct: number | null;
  completeness_pct: number | null;
  customer_service_avg: number | null;
  packaging_avg: number | null;
  recommend_pct: number | null;
};

export type SellerReview = {
  id: string;
  reviewer_id: string | null;
  accuracy: boolean;
  order_completeness: boolean;
  customer_service: number;
  packaging_quality: number;
  overall_rating: number;
  would_recommend: boolean;
  created_at: string;
};

export async function getSeller(id: string): Promise<{
  profile: SellerProfile | null;
  reviews: SellerReview[];
}> {
  try {
    const [profile, reviews] = await Promise.all([
      apiFetch<SellerProfile>(`/api/v1/sellers/${id}`),
      apiFetch<SellerReview[]>(`/api/v1/sellers/${id}/reviews?limit=20`).catch(() => []),
    ]);
    return { profile, reviews };
  } catch {
    return { profile: null, reviews: [] };
  }
}
