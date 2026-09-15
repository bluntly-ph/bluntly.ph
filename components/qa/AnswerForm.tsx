"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";

/**
 * Answer a question (POST /questions/{id}/answers via the BFF).
 *
 * The field is the composers' ("Question Page - Step 2", 4695:14599): white at
 * radius 16 with the card shadow, 14px Regular on 21px lines, an orange line
 * once there is something in it; the pill under it with its trailing arrow.
 * A visitor is sent to log in and brought back to this question.
 */
export function AnswerForm({ questionId, canAnswer }: { questionId: string; canAnswer: boolean }) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!canAnswer) {
    return (
      <Button href={`/login?next=${encodeURIComponent(`/questions/${questionId}`)}`} className="gap-1">
        Log in to answer
        <ArrowRight size={20} aria-hidden="true" />
      </Button>
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
    <form onSubmit={submit}>
      <div className="relative">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value.slice(0, 4000))}
          aria-label="Your answer"
          className={`field-sizing-content block min-h-[156px] w-full resize-none rounded-[16px] border bg-[var(--surface-card)] px-[15px] py-4 text-[14px] leading-[21px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none focus-visible:border-[var(--accent-primary)] ${
            body.trim() ? "border-[rgba(239,88,33,0.8)]" : "border-transparent"
          }`}
        />
        {body.length === 0 ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-4 top-4 text-[14px] leading-[21px] text-[rgba(32,32,32,0.3)]"
          >
            Answer it <em>bluntly</em> here..
          </span>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-[12px] leading-[18px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={!body.trim() || busy} className="mt-4 gap-1">
        {busy ? "Posting…" : "Post answer"}
        {busy ? null : <ArrowRight size={20} aria-hidden="true" />}
      </Button>
    </form>
  );
}

export default AnswerForm;
