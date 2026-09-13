"use client";

import { ArrowLeft } from "@phosphor-icons/react";

import { ProfileNavPanel, type PanelUser } from "@/components/site/ProfileNavPanel";

/**
 * The composer's own header: a back arrow and the avatar, nothing else.
 *
 * Every reviewer frame in the pack draws this, not the site header — no
 * wordmark, no search, no nav. Measured from "Reviewer Page - Step 2.png":
 *
 *   band          y 42..112 on #f2f2f2, 1px rule beneath at rgb(140,140,140)
 *   back arrow    x 27..48, y 69..86 — a 24px glyph, ink-800, centred
 *   avatar        x 326..365, y 58..97 — 40x40 circle, right gutter 24px
 *
 * The arrow replaces the breadcrumb link the form used to draw above the step
 * count ("‹ Star rating"). The destination has not been dropped, only moved
 * out of sight: it is the arrow's accessible name, so a screen reader still
 * hears where back goes while the frame keeps the bare glyph it specifies.
 *
 * The avatar keeps ProfileNavPanel behind it. The frame draws a plain circle,
 * and this is a plain circle — what opens when you press it is behaviour the
 * frame does not speak to, and the composer would otherwise be the one screen
 * in the app with no way to reach navigation.
 */
export function ComposerHeader({
  user,
  onBack,
  backLabel,
}: {
  user: PanelUser;
  /** Omitted on the first screen, where there is nothing to go back to. */
  onBack?: () => void;
  backLabel?: string;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-[rgba(32,32,32,0.5)] bg-[var(--surface-app)]">
      <div className="mx-auto flex h-[71px] w-full max-w-[42rem] items-center justify-between px-6">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            aria-label={backLabel ?? "Go back"}
            className="-ml-2 grid h-11 w-11 cursor-pointer place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <ArrowLeft size={24} aria-hidden="true" />
          </button>
        ) : (
          // Holds the avatar against the right edge on the first screen.
          <span aria-hidden="true" className="h-11 w-11" />
        )}

        <ProfileNavPanel user={user} />
      </div>
    </header>
  );
}

export default ComposerHeader;
