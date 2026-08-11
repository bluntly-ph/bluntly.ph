"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowFatUp } from "@phosphor-icons/react/dist/ssr";

/** Up-vote a review request (raises its platform top-up). Auth via the BFF. */
export function RequestUpvote({
  requestId,
  count,
  canVote,
  myUpvote = false,
}: {
  requestId: string;
  count: number;
  canVote: boolean;
  /** Whether the viewer has already up-voted, from the server (BUG-026). */
  myUpvote?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [n, setN] = useState(count);
  // Seeded from the server: starting at false meant a refresh dropped the
  // highlight, and the next click POSTed an up-vote the unique constraint
  // rejected — which surfaced as a button that greyed out and never resolved.
  const [voted, setVoted] = useState(myUpvote);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (!canVote) {
      // Return here after signing in (BUG-017) — see ReviewVoteBar.
      router.push(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/bff/api/v1/requests/${requestId}/upvote`, {
        method: voted ? "DELETE" : "POST",
      });
      if (res.ok) {
        // Trust the server's own reading of both facts rather than toggling
        // locally, so the button cannot drift from what was actually recorded.
        const r = (await res.json()) as {
          upvote_count: number;
          my_upvote: boolean;
        };
        setN(r.upvote_count);
        setVoted(r.my_upvote);
        setError(null);
      } else {
        // A refusal used to be swallowed: the button simply un-greyed and
        // nothing moved, which is indistinguishable from the click not landing.
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(problem.detail ?? "Couldn't record that vote.");
      }
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={voted}
        aria-label={voted ? "Remove your up-vote" : "Up-vote this request"}
        className={`inline-flex flex-col items-center rounded-[var(--radius-sm)] px-3 py-2 text-[13px] transition-colors disabled:opacity-60 ${
          voted
            ? "bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] text-[var(--accent-primary)]"
            : "bg-[var(--surface-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        <ArrowFatUp size={18} weight={voted ? "fill" : "regular"} />
        <span className="font-semibold">{n}</span>
      </button>
      {error ? (
        <span role="alert" className="max-w-[8rem] text-center text-[11px] text-[var(--accent-danger)]">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export default RequestUpvote;
