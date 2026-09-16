"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Bell, Cube, Warning } from "@phosphor-icons/react/dist/ssr";

import { AdminNav, titleForPath } from "@/components/admin/AdminNav";

/**
 * The admin console shell, built to the Admin Page frames.
 *
 * FRAME PROVENANCE, checked against the live file on 2026-09-16. Of the six
 * node ids this console was built from, four are gone: 4810:16500, 5017:1738
 * (Overview), 5017:3758 (the old Review Queue) and 6532:278 (Answers) all
 * return "node not found". Two remain: 5017:2225 (Admin/Sidebar) and 6922:837
 * (Admin Page - Review Queue), and both were re-read that day.
 *
 * So "1:1 with Figma" can only be asserted for the rail and the review queue.
 * The Overview and the Answers tab stand on their last reading of frames the
 * file no longer has — they are not unverified guesses, but they cannot be
 * re-checked either, and saying so is more useful than a confident citation of
 * a deleted node.
 *
 * The deleted laptop frames were 1280x832 — a viewport rather than a document.
 * That is the shape being built here, and the reason the previous version never
 * read as 1:1: it was one long scrolling page carrying the overview, the whole
 * review queue, the traffic panel and the reports one after another, with the
 * sidebar sliding away as you scrolled.
 *
 * The rules this enforces:
 *
 *   the shell is exactly the viewport      h-dvh, overflow-hidden
 *   the rail never moves                   its own column, full height
 *   the header never moves                 outside the scrolling region
 *   long data scrolls inside its own pane  min-h-0 + overflow-y-auto
 *
 * `min-h-0` is the part that is easy to miss: a flex child defaults to
 * min-height:auto, so without it the workspace grows to fit its content and
 * pushes the document into scrolling anyway — which is exactly the bug.
 */
export function AdminShell({
  moderator,
  urgent,
  children,
}: {
  moderator: { name: string; role: string };
  urgent: number;
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "/moderate";
  const tab = useSearchParams()?.get("tab") ?? null;
  const title = titleForPath(pathname, tab);

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--surface-app)]">
      <AdminNav moderator={moderator} />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 flex-wrap items-center gap-3 px-4 py-4 sm:px-6">
          <h1 className="inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-2.5 text-[18px] font-bold text-[var(--text-primary)] shadow-[var(--shadow-card)]">
            <Cube size={22} weight="regular" />
            {title}
          </h1>

          {urgent > 0 ? (
            <Link
              // Overdue work, which is what `urgent` counts. `?priority=` was
              // the old client-side filter's parameter name and no longer
              // exists — the canonical filters are band / lane / sla / factor.
              href="/moderate/review-queue?sla=overdue"
              className="ml-auto inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-2.5 shadow-[var(--shadow-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
            >
              <Warning size={18} weight="regular" className="text-[var(--accent-danger)]" />
              <span className="text-[14px] font-semibold text-[var(--accent-danger)]">
                {urgent} urgent
              </span>
              <Bell size={20} weight="fill" className="text-[var(--accent-primary)]" />
            </Link>
          ) : null}
        </header>

        {/* The only scrolling region on the page.
            `relative` is load-bearing, not decoration. Tailwind's `sr-only` is
            position:absolute, so a visually-hidden heading with no positioned
            ancestor resolves its containing block to the document, escapes this
            box's overflow:hidden entirely, and extends the page. That is
            precisely what it did: at 1024 one sr-only h2 landed at y=1243 and
            the whole console scrolled 379px, taking the rail with it. Making
            this the containing block clips such descendants here, where they
            belong. */}
        <main className="relative min-h-0 flex-1 overflow-y-auto px-4 pb-8 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
