"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * The two things a reviewer can do to their own contract: toggle auto-renewal,
 * and answer an open buyout offer. Client-side because both mutate on click,
 * going through the BFF (`/api/bff/...`) so the session token stays server-side.
 *
 * Accepting a buyout is irreversible and ends the revenue share, so it asks for
 * a second click rather than firing on the first.
 */
export function ContractActions({
  contractId,
  autoRenew,
  buyoutAmount,
  isActive,
}: {
  contractId: string;
  autoRenew: boolean;
  /** Set only when there is an offer still awaiting an answer. */
  buyoutAmount: string | null;
  isActive: boolean;
}) {
  const router = useRouter();
  const [renew, setRenew] = useState(autoRenew);
  const [pending, setPending] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(path: string, init: RequestInit, key: string) {
    if (pending) return false;
    setPending(key);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/contracts/${contractId}${path}`, init);
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(problem.detail ?? "That didn't go through.");
        return false;
      }
      return true;
    } catch {
      setError("Couldn't reach the server.");
      return false;
    } finally {
      setPending(null);
    }
  }

  async function toggleRenew() {
    const next = !renew;
    const ok = await call(
      "/auto-renew",
      {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ auto_renew: next }),
      },
      "renew",
    );
    if (ok) {
      setRenew(next);
      router.refresh();
    }
  }

  async function answerBuyout(decision: "accept" | "reject") {
    const ok = await call(`/buyout/${decision}`, { method: "POST" }, decision);
    if (ok) {
      setConfirming(false);
      router.refresh();
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-[var(--border-subtle)] pt-4">
      {isActive ? (
        <label className="flex cursor-pointer items-center justify-between gap-3">
          <span>
            <span className="block text-[13px] font-medium text-[var(--text-primary)]">
              Auto-renew
            </span>
            <span className="block text-[12px] text-[var(--text-muted)]">
              Keep earning from this review after the term ends.
            </span>
          </span>
          <input
            type="checkbox"
            checked={renew}
            disabled={pending === "renew"}
            onChange={toggleRenew}
            className="h-5 w-5 shrink-0 accent-[var(--accent-primary)] disabled:opacity-50"
          />
        </label>
      ) : null}

      {buyoutAmount ? (
        <div className="rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-4">
          <p className="text-[13px] font-medium text-[var(--text-primary)]">
            Buyout offered: ₱{buyoutAmount}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-secondary)]">
            Accepting credits your wallet with this amount and ends the revenue
            share on this review for good. Rejecting changes nothing — the
            contract continues.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {confirming ? (
              <>
                <button
                  type="button"
                  onClick={() => answerBuyout("accept")}
                  disabled={pending !== null}
                  className="inline-flex h-9 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-danger)] px-4 text-[13px] font-semibold text-white disabled:opacity-50"
                >
                  {pending === "accept" ? "Accepting…" : "Yes, accept ₱" + buyoutAmount}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  disabled={pending !== null}
                  className="inline-flex h-9 items-center justify-center rounded-[var(--radius-pill)] px-4 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setConfirming(true)}
                  disabled={pending !== null}
                  className="inline-flex h-9 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-4 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--accent-primary-strong)] disabled:opacity-50"
                >
                  Accept buyout
                </button>
                <button
                  type="button"
                  onClick={() => answerBuyout("reject")}
                  disabled={pending !== null}
                  className="inline-flex h-9 items-center justify-center rounded-[var(--radius-pill)] px-4 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] disabled:opacity-50"
                >
                  {pending === "reject" ? "Rejecting…" : "Reject"}
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default ContractActions;
