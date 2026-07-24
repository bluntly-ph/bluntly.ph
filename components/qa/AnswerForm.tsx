"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";

/** Answer a question (POST /questions/{id}/answers via the BFF). */
export function AnswerForm({
  questionId,
  canAnswer,
}: {
  questionId: string;
  canAnswer: boolean;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!canAnswer) {
    return (
      <Link href="/login" className="contents">
        <Button size="sm" variant="secondary">
          Log in to answer
        </Button>
      </Link>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/questions/${questionId}/answers`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ body: body.trim() }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't post your answer.");
        return;
      }
      setBody("");
      router.refresh();
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={3}
        placeholder="Share what you know from actually using it…"
        className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      {error ? <span role="alert" className="text-[12px] text-[var(--accent-danger)]">{error}</span> : null}
      <div>
        <Button type="submit" size="sm" disabled={!body.trim() || busy}>
          {busy ? "Posting…" : "Post answer"}
        </Button>
      </div>
    </form>
  );
}

export default AnswerForm;
