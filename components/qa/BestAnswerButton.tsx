"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SealCheck } from "@phosphor-icons/react/dist/ssr";

/** The asker awards Best Answer (POST /questions/{qid}/answers/{aid}/best). */
export function BestAnswerButton({
  questionId,
  answerId,
}: {
  questionId: string;
  answerId: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function mark() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/bff/api/v1/questions/${questionId}/answers/${answerId}/best`,
        { method: "POST" },
      );
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
      className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--accent-success)] disabled:opacity-60"
    >
      <SealCheck size={14} />
      {busy ? "Marking…" : "Mark best answer"}
    </button>
  );
}

export default BestAnswerButton;
