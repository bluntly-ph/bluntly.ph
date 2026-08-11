"use client";

import { useEffect, useRef, useState } from "react";
import { DotsThree, Flag, LinkSimple } from "@phosphor-icons/react";

/**
 * The three-dot menu in the review top bar (BUG-012).
 *
 * Copy-link rather than the full share sheet: the share control in the action
 * row below already offers `navigator.share`, and two things opening an OS sheet
 * from one screen is confusing. Report links down to the existing dialog rather
 * than duplicating it — one report path, one set of rules.
 */
export function ReviewOverflowMenu({
  title,
  reviewId,
  canReport,
}: {
  title: string;
  reviewId: string;
  canReport: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  // Dismiss on outside click and on Escape — a menu you can only close by
  // picking something from it is a trap.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* Clipboard denied — the visible label simply doesn't change. */
    }
    setOpen(false);
  }

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="More options"
        aria-expanded={open}
        aria-haspopup="menu"
        className="grid h-9 w-9 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
      >
        <DotsThree size={22} weight="bold" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-10 z-20 w-52 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-card)] py-1 shadow-[var(--shadow-card)]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={copyLink}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
          >
            <LinkSimple size={16} />
            Copy link
          </button>
          {canReport ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                // Drives the existing dialog rather than reimplementing it, so
                // there is one report path with one copy of the reasons and the
                // self-report rule.
                document
                  .getElementById(`report-trigger-${reviewId}`)
                  ?.click();
              }}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
            >
              <Flag size={16} />
              Report this review
            </button>
          ) : null}
        </div>
      ) : null}

      <span aria-live="polite" className="sr-only">
        {copied ? `Link to ${title} copied` : ""}
      </span>
    </div>
  );
}

export default ReviewOverflowMenu;
