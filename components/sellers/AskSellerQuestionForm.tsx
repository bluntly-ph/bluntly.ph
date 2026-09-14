"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";

/**
 * Ask the store a question, from its page ("Seller Page - Questions.png").
 *
 * The question is filed against the store (migration 0045), directed at the
 * seller. A claimed store's owner answers under the store's name; until a
 * store is claimed, other buyers are the ones who can answer, and the section
 * above this form says so.
 */
export function AskSellerQuestionForm({
  sellerId,
  signedIn,
}: {
  sellerId: string;
  signedIn: boolean;
}) {
  const router = useRouter();
  const id = useId();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/questions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ seller_id: sellerId, body: body.trim(), directed_to: "seller" }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't post your question.");
        return;
      }
      const created = (await res.json()) as { id: string };
      router.push(`/questions/${created.id}`);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <Link
        href="/login"
        className="mt-3 inline-block text-[13px] font-medium text-[var(--accent-primary)] underline-offset-4 hover:underline"
      >
        Log in to ask this store
      </Link>
    );
  }

  return (
    <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
      <label htmlFor={id} className="sr-only">
        Your question for this store
      </label>
      <textarea
        id={id}
        value={body}
        onChange={(e) => setBody(e.target.value.slice(0, 2000))}
        rows={3}
        placeholder="How long do you usually take to ship?"
        className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      {error ? (
        <p role="alert" className="text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
      <div>
        <Button type="submit" disabled={!body.trim() || busy}>
          {busy ? "Posting…" : "Ask the store"}
        </Button>
      </div>
    </form>
  );
}

export default AskSellerQuestionForm;
