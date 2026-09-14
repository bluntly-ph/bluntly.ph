"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Share, ShareNetwork } from "@phosphor-icons/react";

import { markInteraction } from "@/lib/reading-telemetry-events";

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
 *
 * `variant="icon"` is the Review page frame's round Share (4218:1196): a 32px
 * circle with a 1px outline at 30% ink around a 20px Phosphor Share in
 * --base-gray-400. With no visible label, the status moves into the button's
 * accessible name, so "Link copied" is still announced and still findable.
 */
export function ShareButton({
  title,
  reviewId,
  variant = "label",
}: {
  title: string;
  reviewId: string;
  variant?: "label" | "icon";
}) {
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
        markInteraction(reviewId, "share");
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
      markInteraction(reviewId, "share");
    } catch {
      flash("failed");
    }
  }

  const label =
    status === "copied" ? "Link copied" : status === "failed" ? "Copy failed" : "Share";

  // The icon swap is visual only; screen readers need the change announced.
  const announcement = (
    <span aria-live="polite" className="sr-only">
      {status === "copied"
        ? "Link copied to clipboard"
        : status === "failed"
          ? "Could not copy the link"
          : ""}
    </span>
  );

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={share}
        aria-label={label}
        title={label}
        className="grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-full border border-[var(--line-hairline-30)] text-[var(--base-gray-400)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
      >
        {status === "copied" ? (
          <Check size={20} weight="bold" aria-hidden="true" className="text-[var(--accent-success)]" />
        ) : (
          <Share size={20} aria-hidden="true" />
        )}
        {announcement}
      </button>
    );
  }

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
      {announcement}
    </button>
  );
}

export default ShareButton;
