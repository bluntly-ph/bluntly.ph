"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

/**
 * Approve or reject one seller claim.
 *
 * Approving is a two-step press. There is no un-claim control yet, and an
 * approved claim marks the store as claimed and stops its owner rating it, so
 * a single misclick in a dense table should not be enough to grant that.
 * Rejecting is one press: a rejected claimant can simply try again.
 */
export function SellerClaimDecision({
  claimId,
  sellerName,
}: {
  claimId: string;
  sellerName: string;
}) {
  const router = useRouter();
  const noteId = useId();
  const [note, setNote] = useState("");
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "approve" | "reject") {
    if (busy) return;
    setBusy(decision);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/admin/seller-claims/${claimId}/decision`, {
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
      setArmed(false);
    }
  }

  const pill =
    "h-8 cursor-pointer rounded-[var(--radius-pill)] px-3 text-[12px] font-semibold disabled:cursor-wait disabled:opacity-60";

  return (
    <div className="flex min-w-[15rem] flex-col gap-2">
      <label htmlFor={noteId} className="sr-only">
        Decision note for {sellerName}
      </label>
      <input
        id={noteId}
        value={note}
        onChange={(e) => setNote(e.target.value.slice(0, 2000))}
        placeholder="Note (optional)"
        className="h-8 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-2.5 text-[12px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <div className="flex flex-wrap gap-2">
        {armed ? (
          <button
            type="button"
            onClick={() => decide("approve")}
            disabled={busy !== null}
            className={`${pill} bg-[var(--accent-success)] text-white`}
          >
            {busy === "approve" ? "Approving…" : "Confirm approval"}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setArmed(true)}
            disabled={busy !== null}
            className={`${pill} border border-[var(--accent-success)] text-[var(--text-primary)]`}
          >
            Approve
          </button>
        )}
        <button
          type="button"
          onClick={() => (armed ? setArmed(false) : decide("reject"))}
          disabled={busy !== null}
          className={`${pill} border border-[var(--accent-danger)] text-[var(--accent-danger)]`}
        >
          {armed ? "Cancel" : busy === "reject" ? "Rejecting…" : "Reject"}
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

export default SellerClaimDecision;
