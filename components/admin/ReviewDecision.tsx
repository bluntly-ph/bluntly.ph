"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { LinkSimple } from "@phosphor-icons/react/dist/ssr";

import type { QueueItem } from "@/lib/moderation";

/**
 * The decision controls for one queued review.
 *
 * BUSINESS-REQUIRED / DESIGN-SYSTEM ALIGNED (owner instruction, 2026-09-16).
 * The approved queue frame draws inspection only — a table, a detail column,
 * no verbs — so this panel has no frame to copy and is built from the console's
 * own vocabulary instead: the panel surface, the pill controls and the two-step
 * arming that `SellerClaimDecision` already uses for an outward-facing action.
 *
 * WHAT EACH CONTROL DOES, which is the part that matters here because all three
 * are public and two of them move money:
 *
 *   Publish            `POST /admin/reviews/{id}/publish`. Goes live unmonetized.
 *                      Earn eligibility is decided by the backend, not here:
 *                      2 stars or fewer route to the Honesty Fund, everything
 *                      else is approved. The panel says which before the press.
 *   Monetize & publish `POST /admin/reviews/{id}/referral-link`. Attaches the
 *                      affiliate link and publishes in one transaction, and the
 *                      review becomes revenue-earning for its author.
 *   Reject             `POST /admin/reviews/{id}/reject`. Stays hidden; the
 *                      author is notified with the reason, so the reason is
 *                      required and is written to them verbatim.
 *
 * Publishing is armed before it fires. Rejecting and monetizing are not: each
 * already has a form in front of it that cannot be submitted empty, which is
 * the same friction by another route.
 *
 * The queue holds unpublished, pending reviews only, so unpublish and revoke
 * are deliberately absent — neither can apply to anything on this screen.
 */

const PLATFORMS = ["shopee", "lazada", "amazon", "other"] as const;

type Pending = "publish" | "reject" | "attach" | null;

export function ReviewDecision({ item }: { item: QueueItem }) {
  const router = useRouter();
  const reasonId = useId();
  const urlId = useId();
  const platformId = useId();

  const [mode, setMode] = useState<"reject" | "attach" | null>(null);
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [url, setUrl] = useState("");
  const [platform, setPlatform] = useState<string>(item.suggested_platform ?? "shopee");

  const reviewId = item.review.id;
  const routesToFund = item.review.star_rating <= 2;

  async function send(kind: Exclude<Pending, null>, path: string, body?: unknown) {
    if (busy) return;
    setBusy(kind);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/admin/reviews/${reviewId}/${path}`, {
        method: "POST",
        headers: body ? { "content-type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as {
          detail?: string;
          title?: string;
        };
        setError(problem.detail ?? problem.title ?? "Couldn't record the decision.");
        return;
      }
      // The row leaves the queue, the counts change and the detail pane has to
      // follow. Refreshing the server component is what keeps all three honest —
      // the alternative is this panel deciding locally what the queue now holds.
      setMode(null);
      setArmed(false);
      setReason("");
      setUrl("");
      router.refresh();
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(null);
    }
  }

  const pill =
    "h-8 cursor-pointer rounded-[var(--radius-pill)] px-3 text-[12px] font-semibold " +
    "disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 " +
    "focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";
  const field =
    "h-8 w-full rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-2.5 text-[12px] " +
    "text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none " +
    "placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]";

  return (
    // Pinned to the top of the scrolling detail pane. The `before` strip fills
    // the pane's own 16px padding above the panel, which the evidence would
    // otherwise scroll through; a negative margin would do the same job and
    // give the pane a horizontal scrollbar.
    <section className="sticky top-0 z-10 rounded-[var(--radius-md)] bg-[var(--surface-card)] p-4 shadow-[0_1px_0_var(--line-hairline-10)] before:absolute before:inset-x-0 before:-top-4 before:h-4 before:bg-[var(--surface-card)] before:content-['']">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[12px] font-semibold text-[var(--text-primary)]">Decision</h3>
        <p className="text-[10px] text-[var(--text-muted)]">
          {routesToFund
            ? "2★ or lower — publishing routes this to the Honesty Fund, not to earnings."
            : "Publishing approves this review; it earns only once a link is attached."}
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {armed ? (
          <>
            <button
              type="button"
              onClick={() => void send("publish", "publish")}
              disabled={busy !== null}
              className={`${pill} bg-[var(--accent-success)] text-white`}
            >
              {busy === "publish" ? "Publishing…" : "Confirm publish"}
            </button>
            <button
              type="button"
              onClick={() => setArmed(false)}
              disabled={busy !== null}
              className={`${pill} border border-[var(--base-ink-800)] text-[var(--text-primary)]`}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => {
              setArmed(true);
              setMode(null);
            }}
            disabled={busy !== null}
            className={`${pill} border border-[var(--accent-success)] text-[var(--text-primary)]`}
          >
            Publish
          </button>
        )}

        <button
          type="button"
          onClick={() => {
            setMode(mode === "attach" ? null : "attach");
            setArmed(false);
          }}
          disabled={busy !== null}
          aria-expanded={mode === "attach"}
          className={`${pill} inline-flex items-center gap-1 border border-[var(--accent-primary)] text-[var(--accent-primary)]`}
        >
          <LinkSimple size={14} aria-hidden="true" />
          {mode === "attach" ? "Close link form" : "Monetize & publish"}
        </button>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "reject" ? null : "reject");
            setArmed(false);
          }}
          disabled={busy !== null}
          aria-expanded={mode === "reject"}
          className={`${pill} border border-[var(--accent-danger)] text-[var(--accent-danger)]`}
        >
          {mode === "reject" ? "Close" : "Reject"}
        </button>
      </div>

      {mode === "attach" ? (
        <div className="mt-3 flex flex-col gap-2 rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-3">
          <label htmlFor={urlId} className="text-[11px] text-[var(--text-secondary)]">
            Affiliate link
          </label>
          <input
            id={urlId}
            value={url}
            onChange={(e) => setUrl(e.target.value.slice(0, 2048))}
            placeholder="https://…"
            inputMode="url"
            className={field}
          />
          <label htmlFor={platformId} className="text-[11px] text-[var(--text-secondary)]">
            Platform
          </label>
          <select
            id={platformId}
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className={`${field} cursor-pointer`}
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {item.suggested_sub_id ? (
            <p className="text-[10px] text-[var(--text-secondary)]">
              Sub-ID for the affiliate dashboard:{" "}
              <code className="text-[var(--text-primary)]">{item.suggested_sub_id}</code>.
              A link that does not carry it cannot be attributed when the report
              comes back.
            </p>
          ) : null}
          <button
            type="button"
            onClick={() =>
              void send("attach", "referral-link", {
                url: url.trim(),
                platform,
                sub_id: item.suggested_sub_id,
              })
            }
            disabled={busy !== null || url.trim().length === 0}
            className={`${pill} self-start bg-[var(--accent-primary)] text-white disabled:opacity-60`}
          >
            {busy === "attach" ? "Attaching…" : "Attach & publish"}
          </button>
        </div>
      ) : null}

      {mode === "reject" ? (
        <div className="mt-3 flex flex-col gap-2 rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-3">
          <label htmlFor={reasonId} className="text-[11px] text-[var(--text-secondary)]">
            Reason — sent to the author as written
          </label>
          <textarea
            id={reasonId}
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
            rows={3}
            required
            className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-2.5 text-[12px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
          />
          <p className="text-[10px] text-[var(--text-muted)]">
            {reason.trim().length}/500. The review stays hidden and the author may
            resubmit.
          </p>
          <button
            type="button"
            onClick={() => void send("reject", "reject", { reason: reason.trim() })}
            disabled={busy !== null || reason.trim().length === 0}
            className={`${pill} self-start bg-[var(--accent-danger)] text-white disabled:opacity-60`}
          >
            {busy === "reject" ? "Rejecting…" : "Confirm rejection"}
          </button>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </section>
  );
}

export default ReviewDecision;
