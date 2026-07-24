"use client";

import { useState } from "react";
import { CheckCircle } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";

/**
 * Sets where PayPal payouts are sent (PATCH /auth/me/payout-account). Without it
 * the payout scheduler skips the user, so the dashboard prompts for it.
 */
export function PayoutAccountForm() {
  const [email, setEmail] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/auth/me/payout-account", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ payout_account: email.trim() }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't save that account.");
        return;
      }
      setSaved(true);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <p className="inline-flex items-center gap-2 text-[13px] text-[var(--accent-success)]">
        <CheckCircle size={16} weight="fill" />
        PayPal account saved — you&rsquo;re set to receive payouts.
      </p>
    );
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="your-paypal@email.com"
        className="h-10 flex-1 rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-4 text-[14px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? "Saving…" : "Save PayPal"}
      </Button>
      {error ? (
        <span role="alert" className="text-[12px] text-[var(--accent-danger)]">
          {error}
        </span>
      ) : null}
    </form>
  );
}

export default PayoutAccountForm;
