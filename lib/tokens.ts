import "server-only";

import { apiFetch } from "./api/client";
import { getSessionToken } from "./session";

/**
 * The signed-in reviewer's token balance (BUG-025).
 *
 * The request board escrows a bounty from this balance, so /requests/new has to
 * show it: without it the first signal that you cannot afford a request is a 409
 * `insufficient_tokens` *after* writing the whole thing, and nothing anywhere
 * tells you what you actually have.
 *
 * Note this is `token_balance`, not the peso `wallet_balance` lib/dashboard
 * reads. They are different currencies and must never be shown interchangeably —
 * see the note there on the token economy's retirement everywhere except here,
 * where bounties still spend it.
 *
 * Null means "could not read it", which the caller renders as absence rather
 * than as zero. Showing a confident "0 tokens" to someone who has 400 is worse
 * than showing nothing.
 */
export async function getTokenBalance(): Promise<number | null> {
  const token = await getSessionToken();
  if (!token) return null;
  try {
    const balance = await apiFetch<{ token_balance: number }>(
      "/api/v1/tokens/balance",
      { token },
    );
    return typeof balance?.token_balance === "number" ? balance.token_balance : null;
  } catch {
    return null;
  }
}
