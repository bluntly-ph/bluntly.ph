"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PencilSimple, Plus, Question, Star, X } from "@phosphor-icons/react";
import type { Icon } from "@phosphor-icons/react";

import {
  ACTION_MENU_ITEMS,
  DISABLED_REASON,
  isActionable,
  type ActionMenuItem,
} from "@/components/site/action-menu-model";

/**
 * The floating action menu from "Action Menu.png".
 *
 * NOT MOUNTED ANYWHERE, deliberately. The reference specifies the component and
 * its states, but a scan of all 94 frames found the collapsed FAB in that one
 * export and nowhere else — no page reference establishes a mounting surface.
 * Placing it globally would be an unsupported design assumption, and it would
 * duplicate "Write a review" and "Ask a question", which the profile panel
 * already offers. It is built and ready; when a page reference shows where it
 * belongs, mount this rather than redesigning it.
 *
 * Measured from the reference: a 60x60 collapsed button in brand orange, and an
 * expansion over a black scrim with three labelled actions above a close button.
 *
 * "Rate a Seller" is shown DISABLED rather than hidden — see action-menu-model.
 */

const ICONS: Record<string, Icon> = {
  ask: Question,
  seller: Star,
  review: PencilSimple,
};

export function ActionMenu({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    panelRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const row = (item: ActionMenuItem) => {
    const Glyph = ICONS[item.key] ?? Star;
    const actionable = isActionable(item);
    const circle = actionable
      ? "bg-[var(--accent-primary)] text-white"
      : "bg-[var(--base-gray-500,#8c8c8c)] text-white";

    const label = (
      <span
        className={`rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-4 py-2 text-[14px] shadow-[var(--shadow-card)] ${
          actionable ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"
        }`}
      >
        {item.label}
      </span>
    );
    const glyph = (
      <span className={`grid h-14 w-14 shrink-0 place-items-center rounded-full shadow-[var(--shadow-card)] ${circle}`}>
        <Glyph size={24} weight="bold" aria-hidden="true" />
      </span>
    );

    if (!actionable) {
      return (
        <li key={item.key} className="flex items-center justify-end gap-3">
          {/* A real button carrying `aria-disabled` rather than the `disabled`
              attribute: the design deliberately shows this action exists and is
              unavailable, and `disabled` would drop it out of the tab order so a
              screen-reader user would never learn that. It is announced, focusable
              and inert. */}
          <button
            type="button"
            aria-disabled="true"
            onClick={(e) => e.preventDefault()}
            className="flex cursor-not-allowed items-center gap-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
          >
            {label}
            {glyph}
            <span className="sr-only">{DISABLED_REASON[item.key] ?? "Not available yet"}</span>
          </button>
        </li>
      );
    }

    return (
      <li key={item.key} className="flex items-center justify-end gap-3">
        <Link
          href={item.href as string}
          onClick={() => setOpen(false)}
          className="flex items-center gap-3 no-underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
        >
          {label}
          {glyph}
        </Link>
      </li>
    );
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-haspopup="menu"
        aria-label={open ? "Close actions" : "Actions"}
        className={`fixed bottom-6 right-5 z-30 grid h-[60px] w-[60px] cursor-pointer place-items-center rounded-full bg-[var(--accent-primary)] text-white shadow-[var(--shadow-card)] transition-transform hover:bg-[var(--accent-primary-strong)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] ${className}`}
      >
        <Plus size={26} weight="bold" aria-hidden="true" />
      </button>

      {open
        ? createPortal(
            /* Portalled for the reason ProfileNavPanel is: a non-`none`
               backdrop-filter on an ancestor becomes the containing block for
               `fixed` children, which would trap this against the header box. */
            <>
              <button
                type="button"
                aria-label="Close actions"
                onClick={() => setOpen(false)}
                className="fixed inset-0 z-40 cursor-default bg-[rgba(0,0,0,0.45)]"
              />
              <div
                ref={panelRef}
                id={panelId}
                role="menu"
                aria-label="Actions"
                className="fixed bottom-6 right-5 z-50 flex flex-col items-end gap-4"
              >
                <ul className="flex flex-col gap-4">{ACTION_MENU_ITEMS.map(row)}</ul>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    triggerRef.current?.focus();
                  }}
                  aria-label="Close actions"
                  className="grid h-[60px] w-[60px] cursor-pointer place-items-center rounded-full bg-[color-mix(in_srgb,var(--accent-primary)_70%,white)] text-white shadow-[var(--shadow-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                >
                  <X size={24} weight="bold" aria-hidden="true" />
                </button>
              </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}

export default ActionMenu;
