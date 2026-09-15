"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Medal } from "@phosphor-icons/react/dist/ssr";

/**
 * The asker awards Best Answer (POST /questions/{qid}/answers/{aid}/best).
 * Drawn as the Question Page's "Best Answer" line — a 16px Medal and 12px
 * Light — so the control and the badge it produces read as one thing.
 */
export function BestAnswerButton({ questionId, answerId }: { questionId: string; answerId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function mark() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/bff/api/v1/questions/${questionId}/answers/${answerId}/best`, { method: "POST" });
      if (res.ok) router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={mark}
      disabled={busy}
      className="inline-flex cursor-pointer items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)] hover:text-[var(--accent-success)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] disabled:cursor-wait disabled:opacity-60"
    >
      <Medal size={16} aria-hidden="true" />
      {busy ? "Marking…" : "Mark best answer"}
    </button>
  );
}

export default BestAnswerButton;
