"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowFatDown, ArrowFatUp } from "@phosphor-icons/react/dist/ssr";

import { markInteraction } from "@/lib/reading-telemetry-events";

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
 *
 * Drawn as the Review page frame's vote pill (4218:1196) with the "VoteBar"
 * component's states (6958:944): a 32px pill with a 1px outline at 30% ink,
 * a 20px ArrowFatUp and its 12px Light count, a 26px hairline, then a 20px
 * ArrowFatDown. "The count belongs to the upvote", so the down arrow carries
 * none on screen; its count stays in the button's accessible name. Neutral
 * arrows are --base-gray-400, an upvote is the success green and a downvote the
 * danger red — the file adds Neutral so a voter can tell their vote registered.
 */
export function ReviewVoteBar({
  reviewId,
  helpful,
  unhelpful,
  canVote,
  myVote = null,
}: {
  reviewId: string;
  helpful: number;
  unhelpful: number;
  canVote: boolean;
  /** The viewer's existing vote, from the server (BUG-013). */
  myVote?: "up" | "down" | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [counts, setCounts] = useState({ helpful, unhelpful });
  // Seeded from the server rather than starting empty: this used to mount at
  // null every time, so a refresh silently un-pressed a vote that was still
  // recorded, and voting again POSTed a duplicate the API rejected.
  const [mine, setMine] = useState<"up" | "down" | null>(myVote);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function vote(dir: "up" | "down") {
    if (!canVote) {
      // Carry the return path (BUG-017). proxy.ts sets `?next=` for *route*
      // guards, but this is an in-page action on a public route, so nothing
      // upstream has set it — a bare /login drops the reader on the home page
      // afterwards, away from the review they were voting on.
      router.push(`/login?next=${encodeURIComponent(pathname)}`);
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
      // Both facts come from the server's own reading, so the pressed state
      // cannot drift from what was actually recorded.
      const review = (await res.json()) as {
        helpful_votes: number;
        unhelpful_votes: number;
        my_vote: "up" | "down" | null;
      };
      setCounts({ helpful: review.helpful_votes, unhelpful: review.unhelpful_votes });
      setMine(review.my_vote ?? (remove ? null : dir));
      // Only a cast or changed vote counts as the interaction — removing one
      // is not the fraud-relevant event the marker exists to time.
      if (!remove) markInteraction(reviewId, "vote");
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setPending(false);
    }
  }

  const half =
    "inline-flex h-full cursor-pointer items-center transition-colors hover:bg-[var(--line-hairline-10)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

  return (
    <div className="flex shrink-0 flex-col gap-1">
      <div className="inline-flex h-8 items-center rounded-[20px] border border-[var(--line-hairline-30)]">
        <button
          type="button"
          onClick={() => vote("up")}
          disabled={pending}
          aria-pressed={mine === "up"}
          aria-label={`Helpful, ${compact(counts.helpful)}`}
          className={`${half} gap-1 rounded-l-[20px] pl-3 pr-[5px] text-[12px] font-light leading-none text-[var(--text-primary)]`}
        >
          <ArrowFatUp
            size={20}
            weight="fill"
            aria-hidden="true"
            className={mine === "up" ? "text-[var(--accent-success)]" : "text-[var(--base-gray-400)]"}
          />
          <span aria-hidden="true">{compact(counts.helpful)}</span>
        </button>
        <span aria-hidden="true" className="h-[26px] w-px shrink-0 bg-[var(--line-hairline-30)]" />
        <button
          type="button"
          onClick={() => vote("down")}
          disabled={pending}
          aria-pressed={mine === "down"}
          aria-label={`Not helpful, ${compact(counts.unhelpful)}`}
          className={`${half} rounded-r-[20px] pl-1 pr-3`}
        >
          <ArrowFatDown
            size={20}
            weight="fill"
            aria-hidden="true"
            className={mine === "down" ? "text-[var(--accent-danger)]" : "text-[var(--base-gray-400)]"}
          />
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
