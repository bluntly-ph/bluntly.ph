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
    /** Already served by ReviewOut; the queue screen's Score column and the
     *  detail panel read these rather than inventing a ranking. */
    review_id: string | null;
    photo_url: string | null;
    wilson_score: string;
    helpful_votes: number;
    unhelpful_votes: number;
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

/** One row of the moderation audit log (GET /admin/activity). */
export type ActivityRow = {
  id: string;
  action: string;
  actor: string | null;
  target_type: string | null;
  target_ref: string | null;
  at: string;
};

/** One contributor (GET /admin/reviewers). Carries no email or session data. */
export type ReviewerRow = {
  id: string;
  username: string | null;
  display_name: string | null;
  role: string;
  trust_stage: number;
  reputation_score: string;
  published_reviews: number;
  joined: string;
};

export async function getActivityLog(
  limit = 60,
): Promise<{ rows: ActivityRow[]; total: number } | null> {
  const token = await getSessionToken();
  if (!token) return null;
  return apiFetch<{ rows: ActivityRow[]; total: number }>(
    `/api/v1/admin/activity?limit=${limit}`, { token },
  ).catch(() => null);
}

export async function getReviewers(
  limit = 60,
): Promise<{ rows: ReviewerRow[]; total: number } | null> {
  const token = await getSessionToken();
  if (!token) return null;
  return apiFetch<{ rows: ReviewerRow[]; total: number }>(
    `/api/v1/admin/reviewers?limit=${limit}`, { token },
  ).catch(() => null);
}

/** One scheduled-maintenance execution (GET /admin/cron-runs). */
export type CronRunRow = {
  task: string;
  source: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  processed: number | null;
  failure: string | null;
  detail: string | null;
};

export type TaskHealth = {
  task: string;
  cadence: string;
  /** healthy | due | overdue | failed | never_run */
  state: string;
  period: string;
  due_at: string;
  last_run: CronRunRow | null;
  last_success_at: string | null;
};

export type SchedulerHealth = {
  tasks: TaskHealth[];
  latest: CronRunRow[];
  recent: CronRunRow[];
  never_run: string[];
};

export async function getSchedulerHealth(): Promise<SchedulerHealth | null> {
  const token = await getSessionToken();
  if (!token) return null;
  return apiFetch<SchedulerHealth>("/api/v1/admin/cron-runs?limit=40", { token })
    .catch(() => null);
}
