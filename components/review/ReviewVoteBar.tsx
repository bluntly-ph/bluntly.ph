"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowFatDown, ArrowFatUp } from "@phosphor-icons/react/dist/ssr";

/** Local compact formatter — lib/reviews is server-only, can't import here. */
function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
}

/**
 * Helpfulness voting on a published review. Client-side because it mutates on
 * click, going through the BFF (`/api/bff/...`) so the session token stays on the
 * server. Signed-out visitors are sent to log in; you cannot vote your own review.
 */
export function ReviewVoteBar({
  reviewId,
  helpful,
  unhelpful,
  canVote,
}: {
  reviewId: string;
  helpful: number;
  unhelpful: number;
  canVote: boolean;
}) {
  const router = useRouter();
  const [counts, setCounts] = useState({ helpful, unhelpful });
  const [mine, setMine] = useState<"up" | "down" | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function vote(dir: "up" | "down") {
    if (!canVote) {
      router.push("/login");
      return;
    }
    if (pending) return;
    setPending(true);
    setError(null);
    const remove = mine === dir;
    try {
      const res = await fetch(`/api/bff/api/v1/reviews/${reviewId}/vote`, {
        method: remove ? "DELETE" : "POST",
        headers: remove ? undefined : { "content-type": "application/json" },
        body: remove ? undefined : JSON.stringify({ vote: dir }),
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(problem.detail ?? "Couldn't record your vote.");
        return;
      }
      const review = (await res.json()) as {
        helpful_votes: number;
        unhelpful_votes: number;
      };
      setCounts({ helpful: review.helpful_votes, unhelpful: review.unhelpful_votes });
      setMine(remove ? null : dir);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="inline-flex items-center rounded-[var(--radius-pill)] bg-[var(--surface-card)] shadow-[var(--shadow-hairline-inset)]">
        <button
          type="button"
          onClick={() => vote("up")}
          disabled={pending}
          aria-pressed={mine === "up"}
          aria-label="Helpful"
          className={`inline-flex items-center gap-1.5 rounded-l-[var(--radius-pill)] px-4 py-2 text-[13px] font-medium transition-colors disabled:opacity-60 ${
            mine === "up"
              ? "text-[var(--accent-success)]"
              : "text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
          }`}
        >
          <ArrowFatUp size={16} weight={mine === "up" ? "fill" : "regular"} className="text-[var(--accent-success)]" />
          {compact(counts.helpful)}
        </button>
        <span className="h-5 w-px bg-[var(--line-hairline-10)]" />
        <button
          type="button"
          onClick={() => vote("down")}
          disabled={pending}
          aria-pressed={mine === "down"}
          aria-label="Not helpful"
          className={`inline-flex items-center gap-1.5 rounded-r-[var(--radius-pill)] px-4 py-2 text-[13px] transition-colors disabled:opacity-60 ${
            mine === "down"
              ? "text-[var(--accent-danger)]"
              : "text-[var(--text-muted)] hover:bg-[var(--line-hairline-10)]"
          }`}
        >
          <ArrowFatDown size={16} weight={mine === "down" ? "fill" : "regular"} />
          {compact(counts.unhelpful)}
        </button>
      </div>
      {error ? (
        <span role="alert" className="text-[11px] text-[var(--accent-danger)]">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export default ReviewVoteBar;
