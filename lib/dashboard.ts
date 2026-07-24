import "server-only";

import { apiFetch } from "./api/client";
import { getSessionToken } from "./session";

/**
 * Reviewer earnings data, fetched server-side with the session token. Wallet and
 * token balances, the token ledger, and payouts. Each call is defended so one
 * failing endpoint doesn't blank the whole dashboard.
 */

export type Balance = { token_balance: number; wallet_balance: string };

export type Txn = {
  id: string;
  amount: number;
  balance_after: number;
  kind: string;
  note: string | null;
  created_at: string;
};

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
  transactions: Txn[];
  payouts: Payout[];
}> {
  const token = await getSessionToken();
  if (!token) return { balance: null, transactions: [], payouts: [] };

  const [balance, transactions, payouts] = await Promise.all([
    apiFetch<Balance>("/api/v1/tokens/balance", { token }).catch(() => null),
    apiFetch<Txn[]>("/api/v1/tokens/transactions?limit=12", { token }).catch(() => []),
    apiFetch<Payout[]>("/api/v1/payouts", { token }).catch(() => []),
  ]);
  return { balance, transactions, payouts };
}

/** ₱ with two decimals, from a string-decimal amount (never parse for math). */
export function peso(amount: string | number): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
