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
