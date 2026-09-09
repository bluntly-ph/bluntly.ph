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
  /** This monetized review was edited after its affiliate link was attached. */
  edited_since_monetized?: boolean;
  signals: {
    velocity: boolean;
    collusion: boolean;
    duplicate_content: boolean;
    author_account_age_days: number;
    author_review_count: number;
  };
  /**
   * The server's priority assessment for this card (policy `review-priority-v1`).
   *
   * A sibling of `signals`, never a field inside it: the six advisory signals
   * are frozen by the backend's telemetry-isolation gate. The signals are
   * evidence a moderator reads; this is the policy's decision about where the
   * card sits, and the console renders it rather than deriving its own.
   */
  priority: {
    policy_version: string;
    lane: string;
    score: number;
    band: string;
    sla_state: string;
    due_at: string;
    factors: {
      code: string;
      observed: boolean | number | string;
      contribution: number;
      explanation: string;
    }[];
  };
  /** Which review timestamp stood in for the queue-entry time (no column yet). */
  queue_time_basis?: string;
};

/** Totals over the whole filtered queue, computed before the page was cut. */
export type QueueCounts = {
  total: number;
  by_lane: Record<string, number>;
  by_band: Record<string, number>;
  by_sla: Record<string, number>;
};

/**
 * What the queue screen received.
 *
 * A discriminated result, because "the API failed" and "there is nothing in
 * the queue" must not render the same. They used to: `getQueue` caught every
 * error and returned empty arrays, so an outage drew an empty table under the
 * words "nothing waiting" — the single most reassuring thing a moderation
 * console can say, and in that moment the least true.
 */
export type QueueResult =
  | {
      available: true;
      items: QueueItem[];
      total: number;
      counts: QueueCounts;
      fetchedAt: number;
    }
  | { available: false; reason: "unauthenticated" | "unavailable"; fetchedAt: number };

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

/**
 * One page of the policy-ordered review queue.
 *
 * `query` is the already-validated canonical filter string from
 * `review-queue-model.queueApiQuery` — band, lane, sla, factor, q, limit and
 * offset. Ordering and filtering happen server-side across the whole backlog,
 * so a High-priority review submitted after the first fifty is on page one.
 *
 * `fetchedAt` is when the queue was read, as epoch milliseconds. The screen
 * writes every timestamp as "3s ago" and renders on the server before it
 * hydrates on the client; reading the clock inside the component would give
 * those two renders different answers and tear the table's hydration. Reading
 * it once here also makes it true — these ages are relative to the fetch.
 */
export async function getQueue(query = `limit=${50}`): Promise<QueueResult> {
  const fetchedAt = Date.now();
  const token = await getSessionToken();
  if (!token) return { available: false, reason: "unauthenticated", fetchedAt };
  try {
    const res = await apiFetch<{
      items: QueueItem[];
      total: number;
      counts: QueueCounts;
    }>(`/api/v1/admin/review-queue?${query}`, { token });
    return {
      available: true,
      items: res.items ?? [],
      total: res.total ?? 0,
      counts: res.counts ?? { total: 0, by_lane: {}, by_band: {}, by_sla: {} },
      fetchedAt,
    };
  } catch {
    // Deliberately NOT an empty queue. The caller renders the difference.
    return { available: false, reason: "unavailable", fetchedAt };
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
  /** Queue depth against the policy's SLA targets. `urgent` is the overdue one. */
  approaching_sla?: number;
  overdue_sla?: number;
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
