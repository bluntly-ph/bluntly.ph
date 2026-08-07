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
