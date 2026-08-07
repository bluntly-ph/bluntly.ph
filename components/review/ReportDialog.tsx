"use client";

import { useEffect, useRef, useState } from "react";
import { Flag, X } from "@phosphor-icons/react/dist/ssr";

/**
 * Report a review to the moderators. Client-side because it opens a modal and
 * mutates on submit, going through the BFF (`/api/bff/...`) so the session token
 * stays on the server.
 *
 * The reasons mirror the backend `ModerationReason` enum exactly — a value the
 * API doesn't know is a 422, so these are not free text.
 *
 * Signed-out visitors are sent to log in; the author of a review can't report it
 * (the API rejects self-reports, and the button is hidden rather than letting the
 * user discover that by failing).
 */

const REASONS: { value: string; label: string; hint: string }[] = [
  {
    value: "fake_proof",
    label: "Fake proof of purchase",
    hint: "The receipt or photo looks fabricated or reused.",
  },
  {
    value: "plagiarized",
    label: "Copied from somewhere else",
    hint: "The text appears lifted from another review or site.",
  },
  {
    value: "seller_posing_as_buyer",
    label: "Seller posing as a buyer",
    hint: "The reviewer seems to be selling the product.",
  },
  {
    value: "conflict_of_interest",
    label: "Undisclosed conflict of interest",
    hint: "Sponsored, gifted, or otherwise not independent.",
  },
  { value: "spam", label: "Spam", hint: "Advertising or irrelevant content." },
  {
    value: "harassment",
    label: "Harassment or abuse",
    hint: "Targets a person rather than a product.",
  },
  { value: "other", label: "Something else", hint: "Tell us below." },
];

type State = "idle" | "sending" | "done";

export function ReportDialog({
  reviewId,
  canReport,
}: {
  reviewId: string;
  canReport: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);

  // A <dialog> closed with Escape fires `close` without going through our
  // handler, so reset from the event rather than only from the close button.
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const onClose = () => {
      setError(null);
      if (state === "done") {
        setReason("");
        setNotes("");
        setState("idle");
      }
    };
    el.addEventListener("close", onClose);
    return () => el.removeEventListener("close", onClose);
  }, [state]);

  function open() {
    if (!canReport) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    dialogRef.current?.showModal();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!reason || state === "sending") return;
    setState("sending");
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/reviews/${reviewId}/report`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          reason,
          notes: notes.trim() || null,
        }),
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(problem.detail ?? "Couldn't send your report.");
        setState("idle");
        return;
      }
      setState("done");
    } catch {
      setError("Couldn't reach the server.");
      setState("idle");
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] px-4 py-2.5 text-[13px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--line-hairline-10)] hover:text-[var(--accent-danger)]"
      >
        <Flag size={16} />
        Report
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="report-dialog-title"
        className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-0 text-[var(--text-primary)] shadow-[var(--shadow-sheet)] backdrop:bg-black/40"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] p-5">
          <div>
            <h2
              id="report-dialog-title"
              className="text-[16px] font-semibold text-[var(--text-primary)]"
            >
              Report this review
            </h2>
            <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
              A moderator will look at it. Your name isn&rsquo;t shown to the
              reviewer.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close"
            className="rounded-full p-1 text-[var(--text-muted)] transition-colors hover:bg-[var(--line-hairline-10)]"
          >
            <X size={18} />
          </button>
        </div>

        {state === "done" ? (
          <div className="p-5">
            <p className="text-[14px] text-[var(--text-primary)]">
              Thanks — your report is with the moderators.
            </p>
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="mt-4 inline-flex h-10 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--accent-primary-strong)]"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="p-5">
            <fieldset>
              <legend className="text-[13px] font-medium text-[var(--text-primary)]">
                What&rsquo;s wrong with it?
              </legend>
              <div className="mt-3 flex flex-col gap-1">
                {REASONS.map((r) => (
                  <label
                    key={r.value}
                    className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-sm)] p-2 transition-colors hover:bg-[var(--line-hairline-10)]"
                  >
                    <input
                      type="radio"
                      name="reason"
                      value={r.value}
                      checked={reason === r.value}
                      onChange={() => setReason(r.value)}
                      className="mt-1 accent-[var(--accent-primary)]"
                    />
                    <span>
                      <span className="block text-[13px] font-medium text-[var(--text-primary)]">
                        {r.label}
                      </span>
                      <span className="block text-[12px] text-[var(--text-muted)]">
                        {r.hint}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="mt-4 block">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                Anything to add?{" "}
                <span className="font-normal text-[var(--text-muted)]">
                  (optional)
                </span>
              </span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="What should the moderator look at?"
                className="mt-1.5 w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-3 text-[13px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
              />
            </label>

            {error ? (
              <p role="alert" className="mt-3 text-[12px] text-[var(--accent-danger)]">
                {error}
              </p>
            ) : null}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => dialogRef.current?.close()}
                className="inline-flex h-10 items-center justify-center rounded-[var(--radius-pill)] px-5 text-[13px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--line-hairline-10)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!reason || state === "sending"}
                className="inline-flex h-10 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-danger)] px-5 text-[13px] font-semibold text-white transition-opacity disabled:opacity-50"
              >
                {state === "sending" ? "Sending…" : "Send report"}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </>
  );
}

export default ReportDialog;
