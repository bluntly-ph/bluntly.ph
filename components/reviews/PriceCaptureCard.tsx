"use client";

import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { ArrowRight, Money } from "@phosphor-icons/react";

import { MascotPrompt } from "@/components/reviews/MascotPrompt";
import { Button } from "@/components/ui/Button";

/**
 * "Let's talk money" — the price asked for just before a review is submitted.
 *
 * The reference draws this as a 366x480 CARD, not a 390x844 screen like every
 * numbered composer step, and its own copy says "Skip - continue to submission".
 * So it is an interstitial on the way to submitting, not an eighth step: making
 * it a step would renumber "Step N out of 7" and move the step index stored in
 * every saved draft, which is QA-003's territory for no benefit.
 *
 * Two states, both drawn:
 *   empty   -> the action reads "Skip - continue to submission"
 *   filled  -> the action becomes "Submit"
 * Either way the same submit runs; the price is genuinely optional and always
 * was (`price_paid` is nullable).
 *
 * COPY CORRECTION, recorded deliberately: the frame reads "Your helping us build
 * a database..." — "Your" for "You're". Reproducing a typo is not fidelity, so
 * it ships corrected.
 */
export function PriceCaptureCard({
  open,
  price,
  busy,
  error,
  onPriceChange,
  onSubmit,
  onCancel,
}: {
  open: boolean;
  price: string;
  busy: boolean;
  error: string | null;
  onPriceChange: (next: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const cardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      // Escape backs out to the form rather than submitting — this card is the
      // last point at which a reviewer can still change their mind.
      if (e.key === "Escape" && !busy) {
        e.preventDefault();
        onCancel();
      }
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cardRef.current?.querySelector<HTMLElement>("input")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  const hasPrice = price.trim().length > 0;

  return createPortal(
    <>
      <button
        type="button"
        aria-label="Back to the review"
        onClick={() => !busy && onCancel()}
        className="fixed inset-0 z-40 cursor-default bg-[rgba(32,32,32,0.32)]"
      />
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="fixed left-1/2 top-1/2 isolate z-50 w-[min(23rem,92vw)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-[var(--radius-lg)] bg-[var(--surface-app)] p-6 shadow-[var(--shadow-sheet)]"
      >
        {/* The piggy bank and coin stacks the frame scatters around the
            mascot, at x28..336 y150..274 of its 366-wide card. Lifted from
            "Let's talk money.png" rather than redrawn - the same treatment as
            step 3's clouds - and hidden from assistive tech. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -z-10 h-[125px] w-[309px] select-none bg-contain bg-no-repeat"
          style={{ left: 28, top: 150, backgroundImage: "url(/patterns/money-coins.png)" }}
        />
        <h2 id={titleId} className="text-[20px] font-bold text-[var(--accent-primary)]">
          Let&rsquo;s talk money
        </h2>
        <p className="mt-2 text-[13px] leading-snug text-[var(--text-secondary)]">
          You&rsquo;re helping us build a database that lets users have a more
          well-informed purchase decision.
        </p>

        <MascotPrompt variant="simple" markInset={29} className="mt-5">
          Help users know more about the price!
        </MascotPrompt>

        <label className="mt-5 flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 shadow-[var(--shadow-hairline-inset)]">
          <Money size={20} aria-hidden="true" className="shrink-0 text-[var(--text-muted)]" />
          <span className="sr-only">What did you pay, in pesos?</span>
          {hasPrice ? (
            <span aria-hidden="true" className="text-[15px] text-[var(--text-primary)]">
              ₱
            </span>
          ) : null}
          <input
            value={price}
            onChange={(e) => onPriceChange(e.target.value.replace(/[^0-9.]/g, ""))}
            inputMode="decimal"
            placeholder="How much was it?"
            className="h-12 w-full bg-transparent text-[15px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
          />
        </label>

        {error ? (
          <p role="alert" className="mt-3 text-[13px] text-[var(--accent-danger)]">
            {error}
          </p>
        ) : null}

        {/* Two different controls in the pack, not one restyled. Empty, the
            frame draws Skip as a second field - the same 310x52 white rounded
            row as the price input above it, centred grey text, no border.
            Filled, "Let's talk money-1.png" draws the orange pill. */}
        {hasPrice || busy ? (
          <Button type="button" onClick={onSubmit} disabled={busy} fullWidth className="mt-6">
            {busy ? "Submitting…" : "Submit"}
            {busy ? null : <ArrowRight size={18} weight="bold" aria-hidden="true" />}
          </Button>
        ) : (
          <button
            type="button"
            onClick={onSubmit}
            className="mt-6 h-[52px] w-full cursor-pointer rounded-[var(--radius-md)] bg-[var(--surface-card)] text-center font-[family-name:var(--font-system)] text-[15px] text-[var(--text-muted)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            Skip &ndash; continue to submission
          </button>
        )}
      </div>
    </>,
    document.body,
  );
}

export default PriceCaptureCard;
