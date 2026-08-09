"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ShareNetwork } from "@phosphor-icons/react";

type Status = "idle" | "copied" | "failed";

/**
 * Share a review (BUG-015).
 *
 * The control used to be a bare `<button>` inside a server component, so it
 * rendered but did nothing at all on click.
 *
 * Two paths, picked at click time rather than at render, because
 * `navigator.share` is missing on most desktop browsers and reading it during
 * SSR would hydrate the wrong branch:
 *   * `navigator.share` — the OS sheet. Mobile, and Safari on macOS.
 *   * clipboard — everywhere else, with the label confirming the copy inline.
 *     `alert()` would block the page and reads as an error to most people.
 *
 * A cancelled share sheet throws `AbortError`; that is the user declining, not a
 * failure, so it must not surface as one.
 */
export function ShareButton({ title }: { title: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // A pending reset must not fire after unmount — React would warn, and on a
  // fast back-navigation the node is already gone.
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function flash(next: Status) {
    setStatus(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus("idle"), 2000);
  }

  async function share() {
    const url = window.location.href;

    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (error) {
        // Dismissing the sheet is a normal outcome — say nothing and stop.
        if ((error as Error)?.name === "AbortError") return;
        // Anything else (no permission, unsupported payload) falls through to
        // the clipboard, which is still a useful answer.
      }
    }

    try {
      await navigator.clipboard.writeText(url);
      flash("copied");
    } catch {
      flash("failed");
    }
  }

  const label =
    status === "copied" ? "Link copied" : status === "failed" ? "Copy failed" : "Share";

  return (
    <button
      type="button"
      onClick={share}
      className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] px-4 py-2.5 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
    >
      {status === "copied" ? (
        <Check size={16} weight="bold" className="text-[var(--accent-success)]" />
      ) : (
        <ShareNetwork size={16} />
      )}
      {label}
      {/* The icon swap is visual only; screen readers need the change announced. */}
      <span aria-live="polite" className="sr-only">
        {status === "copied"
          ? "Link copied to clipboard"
          : status === "failed"
            ? "Could not copy the link"
            : ""}
      </span>
    </button>
  );
}

export default ShareButton;
