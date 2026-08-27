import "server-only";

import { apiFetch } from "./api/client";
import { getSessionToken } from "./session";

/**
 * Reviewer earnings data, fetched server-side with the session token: the PHP
 * wallet balance and the payout history. Each call is defended so one failing
 * endpoint doesn't blank the whole dashboard.
 *
 * The token ledger (`/tokens/transactions`) is deliberately NOT read here. Its
 * `amount` is an integer token count, not pesos, and the token economy was
 * retired in favour of the PHP revenue share — surfacing it next to peso figures
 * read as money and wasn't. `/tokens/balance` is still the only source of
 * `wallet_balance`, so it stays; only `token_balance` is ignored.
 */

export type Balance = { token_balance: number; wallet_balance: string };

export type Payout = {
  id: string;
  amount: string;
  currency: string;
  status: string;
  scheduled_for: string;
  paid_at: string | null;
  created_at: string;
};

/** Minimum PHP wallet balance before a payout can be scheduled (PAYOUT_MIN_PHP). */
export const PAYOUT_MIN_PHP = 300;

export async function getDashboard(): Promise<{
  balance: Balance | null;
  payouts: Payout[];
}> {
  const token = await getSessionToken();
  if (!token) return { balance: null, payouts: [] };

  const [balance, payouts] = await Promise.all([
    apiFetch<Balance>("/api/v1/tokens/balance", { token }).catch(() => null),
    apiFetch<Payout[]>("/api/v1/payouts", { token }).catch(() => []),
  ]);
  return { balance, payouts };
}

/** ₱ with two decimals, from a string-decimal amount (never parse for math). */
export function peso(amount: string | number): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export type DashboardSeriesPoint = { day: string; amount: string };

export type DashboardReviewRow = {
  review_id: string;
  title: string;
  photo_url: string | null;
  earnings: string;
  views: number;
  helped: number;
  series: DashboardSeriesPoint[];
};

export type DashboardSummary = {
  range: string;
  window_start: string;
  window_end: string;
  estimated_commission: string;
  earned_in_window: string;
  total_views: number;
  /** Null while nothing measures read time; `unavailable` names it. */
  average_read_seconds: number | null;
  unavailable: string[];
  has_earnings: boolean;
  series: DashboardSeriesPoint[];
  reviews: DashboardReviewRow[];
};

export const DASHBOARD_RANGES = [
  { key: "7d", label: "This week" },
  { key: "30d", label: "This month" },
  { key: "90d", label: "Last 90 days" },
] as const;

export async function getDashboardSummary(
  range: string,
): Promise<DashboardSummary | null> {
  const token = await getSessionToken();
  if (!token) return null;
  const key = DASHBOARD_RANGES.some((r) => r.key === range) ? range : "7d";
  return apiFetch<DashboardSummary>(
    `/api/v1/users/me/dashboard?range=${key}`, { token },
  ).catch(() => null);
}

/**
 * Compact counts, the way the design writes them: "47k views", "1.3k helped".
 *
 * Below 1000 the exact number is short enough to be worth keeping — "900
 * helped" is more useful than "0.9k".
 */
export function compactCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) {
    const k = n / 1000;
    return `${k < 10 ? k.toFixed(1).replace(/\.0$/, "") : Math.round(k)}k`;
  }
  const m = n / 1_000_000;
  return `${m < 10 ? m.toFixed(1).replace(/\.0$/, "") : Math.round(m)}m`;
}

/** ₱ with no decimals — the list rows in the design read "₱536", not "₱536.00". */
export function pesoWhole(amount: string | number): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  return `₱${Math.round(n).toLocaleString("en-PH")}`;
}

export type EarningBreakdown = {
  gross_amount: string;
  commission_rate: string | null;
  platform_share: string;
  honesty_fund_share: string;
  reviewer_share: string;
};

export type EarningRow = {
  commission_id: string;
  occurred_on: string;
  review_id: string | null;
  review_title: string | null;
  product_name: string | null;
  photo_url: string | null;
  amount: string;
  /** pending | to_earn | paid | returned */
  status: string;
  breakdown: EarningBreakdown;
};

export type EarningsHistory = {
  all_time: string;
  counts: Record<string, number>;
  rows: EarningRow[];
  has_data: boolean;
};

/**
 * The History frame's filter tabs.
 *
 * These are the reviewer-facing reading of the canonical pair, not the
 * canonical vocabulary itself — "To earn" is a completed sale that has not been
 * paid, which is exactly the distinction a reviewer needs and exactly what
 * "Completed" would blur.
 */
/**
 * The tabs frame 5762:472 actually draws: All / Pending / To earn / Returned.
 *
 * `paid` is a real settlement state and the API serves it, but the frame has no
 * tab for it, so it is reachable by URL rather than shown as a fifth tab that
 * the design does not have. Paid rows still appear under All.
 */
export const EARNING_TABS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "to_earn", label: "To earn" },
  { key: "returned", label: "Returned" },
] as const;

/** Every filter the API accepts, including the one with no tab. */
export const EARNING_FILTERS = ["all", "pending", "to_earn", "paid", "returned"];

/**
 * Sum peso strings exactly, in centavos.
 *
 * The shares are rounded independently when they are written, so adding them as
 * floats can land a centavo out on a screen whose entire job is showing a
 * reviewer where their money went.
 */
export function sumPeso(...values: (string | null | undefined)[]): string {
  const centavos = values.reduce((total, v) => {
    if (!v) return total;
    const [whole, frac = ""] = String(v).replace(/[^0-9.-]/g, "").split(".");
    const sign = whole.trim().startsWith("-") ? -1 : 1;
    const w = Math.abs(parseInt(whole, 10) || 0);
    const c = parseInt((frac + "00").slice(0, 2), 10) || 0;
    return total + sign * (w * 100 + c);
  }, 0);
  return (centavos / 100).toFixed(2);
}

/** Badge tone per status. Each badge also carries its own words. */
export const EARNING_TONE: Record<string, string> = {
  pending: "bg-[var(--accent-star)]/15 text-[var(--accent-star)]",
  to_earn: "bg-[var(--accent-success)]/15 text-[var(--accent-success)]",
  paid: "bg-[var(--accent-trust)]/15 text-[var(--accent-trust)]",
  returned: "bg-[var(--accent-danger)]/15 text-[var(--accent-danger)]",
};

export const EARNING_LABEL: Record<string, string> = {
  pending: "Pending",
  to_earn: "To earn",
  paid: "Paid",
  returned: "Returned",
};

export async function getEarnings(
  status: string,
): Promise<EarningsHistory | null> {
  const token = await getSessionToken();
  if (!token) return null;
  const key = EARNING_FILTERS.includes(status) ? status : "all";
  return apiFetch<EarningsHistory>(
    `/api/v1/users/me/earnings?status=${key}`, { token },
  ).catch(() => null);
}

/**
 * The Insights contribution streak (frame 5762:752).
 *
 * Owner decision, 2026-08-27: this counts days the reviewer CONTRIBUTED —
 * published a review, asked a question, answered one, or submitted a price
 * observation. It is not an attendance metric, and nothing here tracks reading
 * or browsing. Every date comes from a timestamp the backend already stores.
 */
export type StreakDay = { day: string; contributed: boolean };

export type ContributionStreak = {
  current_streak: number;
  last_contribution: string | null;
  active_today: boolean;
  total_days: number;
  calendar_month: string;
  calendar: StreakDay[];
};

export async function getStreak(): Promise<ContributionStreak | null> {
  const token = await getSessionToken();
  if (!token) return null;
  return apiFetch<ContributionStreak>("/api/v1/users/me/streak", { token })
    .catch(() => null);
}
