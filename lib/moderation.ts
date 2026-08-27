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
    /** Proof of purchase was submitted. Never its location — moderators fetch
     *  the object itself from GET /reviews/{id}/receipt, which authorizes the
     *  caller and returns a short-lived signed URL. */
    has_receipt: boolean;
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

/** One filed report in the moderator queue (GET /admin/reports). */
export type ReportItem = {
  report: {
    id: string;
    log_id: string | null;
    target_type: string | null;
    target_ref: string | null;
    reason: string | null;
    notes: string | null;
    evidence_url: string | null;
    created_at: string;
  };
  reporter: {
    id: string;
    display_name: string | null;
    username: string | null;
    trust_stage: number;
  } | null;
  target: {
    id: string;
    title: string | null;
    author_id: string | null;
    is_published: boolean;
  } | null;
  target_report_count: number;
};

/** Reader-facing labels for the backend `ModerationReason` enum. */
export const REPORT_REASON_LABELS: Record<string, string> = {
  fake_proof: "Fake proof of purchase",
  plagiarized: "Copied from elsewhere",
  spam: "Spam",
  harassment: "Harassment or abuse",
  conflict_of_interest: "Undisclosed conflict of interest",
  seller_posing_as_buyer: "Seller posing as a buyer",
  other: "Something else",
};

/**
 * Reports filed by the community, newest first. Defended like the review queue:
 * a failing reports endpoint must not blank the whole moderation page.
 */
export async function getReports(): Promise<ReportItem[]> {
  const token = await getSessionToken();
  if (!token) return [];
  try {
    const res = await apiFetch<{ items: ReportItem[]; total: number }>(
      "/api/v1/admin/reports?limit=50",
      { token },
    );
    return res.items;
  } catch {
    return [];
  }
}

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

export type AdminOverviewData = {
  queue_total: number;
  high_priority: number;
  approved_today: number;
  approved_delta: number;
  pending_affiliate: number;
  honesty_fund_pool: string;
  honesty_fund_month: string;
  urgent: number;
  breakdown: { label: string; count: number }[];
  affiliate: {
    lifecycle: { label: string; count: number }[];
    settlement: { label: string; count: number }[];
    recognised_amount: string;
    reversed_amount: string;
    unrecovered_amount: string;
    has_data: boolean;
  };
  activity: {
    action: string;
    actor: string | null;
    target_ref: string | null;
    at: string;
  }[];
  /** Sections the backend could not compute for this request. */
  unavailable?: string[];
};

export async function getAdminOverview(): Promise<AdminOverviewData | null> {
  const token = await getSessionToken();
  if (!token) return null;
  return apiFetch<AdminOverviewData>("/api/v1/admin/analytics/overview", { token })
    .catch(() => null);
}
