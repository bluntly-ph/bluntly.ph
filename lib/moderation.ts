import "server-only";

import { apiFetch } from "./api/client";
import { getSessionToken } from "./session";

/** One card in the moderator queue (GET /admin/review-queue). */
export type QueueItem = {
  review: {
    id: string;
    title: string;
    discussion: string;
    verdict: "yes_absolutely" | "it_depends" | "hard_pass";
    star_rating: number;
    verification_status: "verified" | "unverified";
    created_at: string;
  };
  product: {
    id: string;
    canonical_name: string | null;
    source_url: string | null;
    platforms: { platform: string; is_monetizable: boolean }[];
  };
  author: {
    id: string;
    display_name: string | null;
    trust_stage: number;
    reputation_score: string;
  } | null;
  suggested_platform: string | null;
  suggested_sub_id: string | null;
  signals: {
    velocity: boolean;
    collusion: boolean;
    duplicate_content: boolean;
    author_account_age_days: number;
    author_review_count: number;
  };
};

export async function getQueue(): Promise<{
  pending: QueueItem[];
  edited: QueueItem[];
}> {
  const token = await getSessionToken();
  if (!token) return { pending: [], edited: [] };
  try {
    const res = await apiFetch<{
      pending: QueueItem[];
      edited_since_monetized: QueueItem[];
    }>("/api/v1/admin/review-queue?limit=50", { token });
    return { pending: res.pending, edited: res.edited_since_monetized };
  } catch {
    return { pending: [], edited: [] };
  }
}
