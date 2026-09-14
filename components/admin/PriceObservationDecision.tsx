"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

/**
 * Approve or reject one community price.
 *
 * One press each. A single approved price moves a median of at least three,
 * and a queue of prices is worked through quickly, so a confirm step would
 * cost more than it protects. The API refuses a moderator deciding their own.
 */
export function PriceObservationDecision({
  observationId,
  label,
}: {
  observationId: string;
  label: string;
}) {
  const router = useRouter();
  const noteId = useId();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "approve" | "reject") {
    if (busy) return;
    setBusy(decision);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/admin/price-observations/${observationId}/decision`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision, note: note.trim() || null }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't record the decision.");
        return;
      }
      router.refresh();
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(null);
    }
  }

  const pill =
    "h-8 cursor-pointer rounded-[var(--radius-pill)] px-3 text-[12px] font-semibold disabled:cursor-wait disabled:opacity-60";

  return (
    <div className="flex min-w-[14rem] flex-col gap-2">
      <label htmlFor={noteId} className="sr-only">
        Decision note for {label}
      </label>
      <input
        id={noteId}
        value={note}
        onChange={(e) => setNote(e.target.value.slice(0, 2000))}
        placeholder="Note (optional)"
        className="h-8 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-2.5 text-[12px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => decide("approve")}
          disabled={busy !== null}
          className={`${pill} bg-[var(--accent-success)] text-white`}
        >
          {busy === "approve" ? "Approving…" : "Approve"}
        </button>
        <button
          type="button"
          onClick={() => decide("reject")}
          disabled={busy !== null}
          className={`${pill} border border-[var(--accent-danger)] text-[var(--accent-danger)]`}
        >
          {busy === "reject" ? "Rejecting…" : "Reject"}
        </button>
      </div>
      {error ? (
        <p role="alert" className="text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default PriceObservationDecision;
