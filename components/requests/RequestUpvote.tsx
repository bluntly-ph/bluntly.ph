"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowFatUp } from "@phosphor-icons/react/dist/ssr";

/** Up-vote a review request (raises its platform top-up). Auth via the BFF. */
export function RequestUpvote({
  requestId,
  count,
  canVote,
}: {
  requestId: string;
  count: number;
  canVote: boolean;
}) {
  const router = useRouter();
  const [n, setN] = useState(count);
  const [voted, setVoted] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    if (!canVote) {
      router.push("/login");
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/bff/api/v1/requests/${requestId}/upvote`, {
        method: voted ? "DELETE" : "POST",
      });
      if (res.ok) {
        const r = (await res.json()) as { upvote_count: number };
        setN(r.upvote_count);
        setVoted(!voted);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={voted}
      className={`inline-flex flex-col items-center rounded-[var(--radius-sm)] px-3 py-2 text-[13px] transition-colors disabled:opacity-60 ${
        voted
          ? "bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] text-[var(--accent-primary)]"
          : "bg-[var(--surface-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      }`}
    >
      <ArrowFatUp size={18} weight={voted ? "fill" : "regular"} />
      <span className="font-semibold">{n}</span>
    </button>
  );
}

export default RequestUpvote;
