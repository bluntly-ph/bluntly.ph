"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

/**
 * A moderator's remove control on a seller review.
 *
 * Seller reviews publish without the product-review gate (DEVIATIONS §37), so
 * this is where they are moderated. The API refuses anyone below moderator and
 * refuses a moderator removing their own rating or one of a store they run;
 * this control is only rendered for moderators, but the API is the guard.
 */
export function RemoveSellerReviewButton({ reviewId }: { reviewId: string }) {
  const router = useRouter();
  const noteId = useId();
  const [armed, setArmed] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/admin/seller-reviews/${reviewId}/removal`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ note: note.trim() || null }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't remove this review.");
        return;
      }
      router.refresh();
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  if (!armed) {
    return (
      <button
        type="button"
        onClick={() => setArmed(true)}
        className="mt-3 cursor-pointer text-[12px] text-[var(--text-muted)] underline-offset-4 hover:text-[var(--accent-danger)] hover:underline"
      >
        Remove as moderator
      </button>
    );
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <label htmlFor={noteId} className="sr-only">
        Reason for removal
      </label>
      <input
        id={noteId}
        value={note}
        onChange={(e) => setNote(e.target.value.slice(0, 2000))}
        placeholder="Reason (optional)"
        className="h-8 min-w-0 flex-1 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-2.5 text-[12px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        className="h-8 cursor-pointer rounded-[var(--radius-pill)] bg-[var(--accent-danger)] px-3 text-[12px] font-semibold text-white disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? "Removing…" : "Remove review"}
      </button>
      <button
        type="button"
        onClick={() => setArmed(false)}
        className="cursor-pointer text-[12px] text-[var(--text-secondary)] underline-offset-4 hover:underline"
      >
        Cancel
      </button>
      {error ? (
        <p role="alert" className="w-full text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default RemoveSellerReviewButton;
