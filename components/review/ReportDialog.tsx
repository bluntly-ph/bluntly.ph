"use client";

import { useEffect, useRef, useState } from "react";
import { Flag, X } from "@phosphor-icons/react/dist/ssr";

import { markInteraction } from "@/lib/reading-telemetry-events";

/**
 * Report a review to the moderators. Client-side because it opens a modal and
 * mutates on submit, going through the BFF (`/api/bff/...`) so the session token
 * stays on the server.
 *
 * NO FIGMA FRAME: the file has no report component. It is set as the file's
 * sheets are ("Sort", 1591:5408) — radius 20 in the page colour, the glyph and
 * a 16px Bold title over a 30% hairline, 20px ring radios filled brand when
 * chosen with 16px Light labels, the composers' 14px field, and the text
 * action against a 38px pill — so reporting reads as part of the same product.
 * The pill stays danger red: sending a report is not a neutral action.
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

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";
const TEXT_ACTION = `cursor-pointer text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)] ${FOCUS}`;
const PILL = `h-[38px] cursor-pointer rounded-[20px] px-3 text-[16px] leading-none tracking-[0.8px] text-[var(--text-on-brand)] ${FOCUS}`;

export function ReportDialog({
  reviewId,
  canReport,
  hideTrigger = false,
}: {
  reviewId: string;
  canReport: boolean;
  /**
   * Keep the trigger out of sight. The Review page frame (4218:1196) has no
   * Report button in its action row: reporting lives in the bar's overflow
   * menu, which opens this dialog through the trigger's id. `.click()` still
   * fires on a hidden element, so there remains exactly one report path.
   */
  hideTrigger?: boolean;
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
      markInteraction(reviewId, "report");
    } catch {
      setError("Couldn't reach the server.");
      setState("idle");
    }
  }

  return (
    <>
      <button
        type="button"
        hidden={hideTrigger}
        onClick={open}
        // Addressable so the overflow menu in the top nav can open this same
        // dialog (BUG-012) instead of there being a second report path with its
        // own copy of the reasons and the self-report rule.
        id={`report-trigger-${reviewId}`}
        className={`inline-flex h-8 cursor-pointer items-center gap-1 rounded-[16px] border border-[var(--text-primary)] px-[11px] text-[12px] font-light leading-none text-[var(--text-primary)] hover:border-[var(--accent-danger)] hover:text-[var(--accent-danger)] ${FOCUS}`}
      >
        <Flag size={20} weight="light" aria-hidden="true" />
        Report
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="report-dialog-title"
        className="m-auto max-h-[90dvh] w-[min(390px,calc(100vw-2rem))] overflow-y-auto rounded-[20px] bg-[var(--surface-app)] p-0 text-[var(--text-primary)] shadow-[var(--shadow-sheet)] backdrop:bg-[var(--overlay-scrim-25)]"
      >
        <div className="flex items-start gap-2 px-6 pt-6">
          <Flag size={20} aria-hidden="true" className="shrink-0" />
          <div className="min-w-0 flex-1">
            <h2 id="report-dialog-title" className="mt-0.5 text-[16px] font-bold leading-none">
              Report this review
            </h2>
            <p className="mt-2 text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
              A moderator will look at it. Your name isn&rsquo;t shown to the reviewer.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close"
            className={`-my-2 -mr-2 grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-full hover:bg-[var(--line-hairline-10)] ${FOCUS}`}
          >
            <X size={28} aria-hidden="true" />
          </button>
        </div>
        <hr className="mx-6 mt-[22px] border-0 border-t border-[var(--line-hairline-30)]" />

        {state === "done" ? (
          <div className="px-6 pb-8 pt-[15px]">
            <p className="text-[14px] leading-[21px]">Thanks — your report is with the moderators.</p>
            <div className="mt-[38px] flex justify-end">
              <button
                type="button"
                onClick={() => dialogRef.current?.close()}
                className={`${PILL} bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-strong)]`}
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="px-6 pb-8 pt-[15px]">
            <fieldset className="min-w-0">
              <legend className="text-[16px] font-semibold leading-none">What&rsquo;s wrong with it?</legend>
              <div className="mt-6 flex flex-col gap-[14px]">
                {REASONS.map((r) => (
                  <label key={r.value} className="relative flex cursor-pointer items-start gap-3">
                    <input
                      type="radio"
                      name="reason"
                      value={r.value}
                      checked={reason === r.value}
                      onChange={() => setReason(r.value)}
                      className="peer sr-only"
                    />
                    <span
                      aria-hidden="true"
                      className="h-5 w-5 shrink-0 rounded-full border border-[var(--line-hairline-30)] peer-checked:bg-[var(--accent-primary)] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent-primary)]"
                    />
                    <span className="min-w-0 pt-0.5">
                      <span className="block text-[16px] font-light leading-none">{r.label}</span>
                      <span className="mt-1.5 block text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
                        {r.hint}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="mt-7 block">
              <span className="text-[16px] font-semibold leading-none">
                Anything to add? <span className="text-[12px] font-light text-[rgba(32,32,32,0.7)]">(optional)</span>
              </span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="What should the moderator look at?"
                className="mt-3 block min-h-[96px] w-full resize-y rounded-[16px] border border-transparent bg-[var(--surface-card)] px-[15px] py-3 text-[14px] leading-[21px] shadow-[var(--shadow-card)] outline-none placeholder:text-[rgba(32,32,32,0.3)] focus-visible:border-[var(--accent-primary)]"
              />
            </label>

            {error ? (
              <p role="alert" className="mt-3 text-[12px] leading-[18px] text-[var(--accent-danger)]">
                {error}
              </p>
            ) : null}

            <div className="mt-[38px] flex items-center justify-between">
              <button type="button" onClick={() => dialogRef.current?.close()} className={TEXT_ACTION}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={!reason || state === "sending"}
                className={`${PILL} bg-[var(--accent-danger)] disabled:cursor-not-allowed disabled:bg-[var(--disabled-surface)] disabled:text-[var(--disabled-text)]`}
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
