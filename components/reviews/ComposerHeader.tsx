"use client";

import { ArrowLeft } from "@phosphor-icons/react";

import { ProfileNavPanel, type PanelUser } from "@/components/site/ProfileNavPanel";

/**
 * The composer's own header: Figma "NavBar" type Flow (7020:1269) with the
 * flow's "Progress bar" line, as every "Reviewer Page - Step" frame draws it
 * (read 2026-09-15).
 *
 *   bar        72px on --surface-app; a 28px ArrowLeft 24px in, the 40px avatar
 *              24px from the right
 *   progress   a 1px line on the bar's bottom edge: #8c8c8c (--base-gray-400)
 *              with the completed share of the flow in --accent-primary over
 *              it — 220 of 390px on step 4 of 7 — and the whole line in
 *              --accent-success once the last step is reached
 *
 * The arrow's accessible name says where back goes, so a screen reader hears
 * the destination the bare glyph does not show. The avatar keeps
 * ProfileNavPanel behind it: the composer would otherwise be the one screen with
 * no way to reach navigation.
 */
export function ComposerHeader({
  user,
  onBack,
  backLabel,
  progress = 0,
}: {
  user: PanelUser;
  /** Omitted on the first screen, where there is nothing to go back to. */
  onBack?: () => void;
  backLabel?: string;
  /** Share of the flow completed, 0..1. */
  progress?: number;
}) {
  const share = Math.max(0, Math.min(1, progress));
  return (
    <header className="sticky top-0 z-30 bg-[var(--surface-app)]">
      <div className="mx-auto flex h-[72px] w-full max-w-[42rem] items-center justify-between px-6">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            aria-label={backLabel ?? "Go back"}
            className="-ml-2 grid h-11 w-11 cursor-pointer place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <ArrowLeft size={28} aria-hidden="true" />
          </button>
        ) : (
          // Holds the avatar against the right edge on the first screen.
          <span aria-hidden="true" className="h-11 w-11" />
        )}

        <ProfileNavPanel user={user} />
      </div>
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-[var(--base-gray-400)]">
        {share > 0 ? (
          <div
            className={`h-full ${share >= 1 ? "bg-[var(--accent-success)]" : "bg-[var(--accent-primary)]"}`}
            style={{ width: `${share * 100}%` }}
          />
        ) : null}
      </div>
    </header>
  );
}

/**
 * The graph paper every composer frame lays under its content — Figma "image
 * 15" at 10%, from the bar down. Fixed, so it holds still while a long step
 * scrolls. It sits at -z-10, so the page wrapper must not paint its own
 * background over it; the body already carries --surface-app.
 */
export function ComposerGrid() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 bottom-0 top-[72px] -z-10 bg-[url('/figma/landing/hero-grid.png')] bg-[length:390px_633px] opacity-10"
    />
  );
}

export default ComposerHeader;
