"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PencilSimpleLine, Plus, QuestionMark, Star, X } from "@phosphor-icons/react";
import type { Icon, IconWeight } from "@phosphor-icons/react";

import {
  ACTION_MENU_ITEMS,
  DISABLED_REASON,
  isActionable,
  type ActionMenuItem,
} from "@/components/site/action-menu-model";

/**
 * The floating action menu from "Action Menu.png" — phones only.
 *
 * MOUNTED on the discovery surfaces (home, feed, search, categories, questions,
 * a review, a store) at the owner's direction on 2026-09-14, so QA can start all
 * three workflows from a phone. The frames draw it on the search page's
 * Questions tab (live canvas), the questions index and both seller-page tabs.
 * Hidden from `md` (768px) up: no reference places it on tablet or desktop,
 * where the header already carries these actions. Never mounted on the
 * composers it opens.
 *
 * Measured from the frame at 390x844 (.bluntly-autopilot/figma-reference/
 * ACTION-MENU.md):
 *   collapsed  60x60 disc in --brand-600, 32px from the right and bottom edges,
 *              a 27px plus drawn with a 2px stroke, --shadow-card
 *   expanded   black scrim at 25%; action discs on an 80px pitch (20px gaps)
 *              with the close disc, in --brand-400, taking the FAB's place;
 *              label pills 40px tall, 12px radius, --surface-app, 12px from
 *              their disc, 16px type with an 11px cap height; glyphs in
 *              --surface-app: a bare question mark, a star, a pencil on a line
 *
 * INTENTIONAL PRODUCT DIFFERENCE: the frame draws the "Rate a Seller" star in
 * grey, because it was drawn while no seller entity existed. The owner has since
 * enabled the action, so its glyph matches the other two rather than reading as
 * unavailable.
 *
 * A disclosure, not an ARIA menu: the panel is a list of ordinary links, which
 * `role="menu"` would misdescribe to a screen reader.
 */

const GLYPHS: Record<string, { icon: Icon; size: number; weight: IconWeight }> = {
  ask: { icon: QuestionMark, size: 28, weight: "regular" },
  seller: { icon: Star, size: 28, weight: "fill" },
  review: { icon: PencilSimpleLine, size: 28, weight: "regular" },
};

/** The frame's 32px corner, kept clear of a notch or home indicator. */
const CORNER =
  "bottom-[calc(32px_+_env(safe-area-inset-bottom))] right-[calc(32px_+_env(safe-area-inset-right))]";

const DISC =
  "grid h-[60px] w-[60px] shrink-0 place-items-center rounded-full text-[var(--surface-app)] shadow-[var(--shadow-card)]";

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

export function ActionMenu() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

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
    const glyph = GLYPHS[item.key] ?? GLYPHS.seller;
    const Glyph = glyph.icon;
    const actionable = isActionable(item);

    const content = (
      <>
        <span
          className={`flex h-10 items-center rounded-[var(--radius-sm)] bg-[var(--surface-app)] pl-4 pr-[5px] text-[16px] tracking-[0.05em] ${
            actionable ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"
          }`}
        >
          {item.label}
        </span>
        <span className={`${DISC} bg-[var(--accent-primary)]`}>
          <Glyph
            size={glyph.size}
            weight={glyph.weight}
            aria-hidden="true"
            className={actionable ? undefined : "text-[var(--base-gray-300)]"}
          />
        </span>
      </>
    );

    if (!actionable) {
      return (
        <li key={item.key} className="flex justify-end">
          {/* `aria-disabled` rather than `disabled`, so an unavailable action
              stays in the tab order and is announced rather than vanishing. */}
          <button
            type="button"
            aria-disabled="true"
            onClick={(e) => e.preventDefault()}
            className={`flex cursor-not-allowed items-center gap-3 ${FOCUS}`}
          >
            {content}
            <span className="sr-only">{DISABLED_REASON[item.key] ?? "Not available yet"}</span>
          </button>
        </li>
      );
    }

    return (
      <li key={item.key} className="flex justify-end">
        <Link
          href={item.href as string}
          onClick={() => setOpen(false)}
          className={`flex items-center gap-3 no-underline ${FOCUS}`}
        >
          {content}
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
        aria-label="Actions"
        className={`fixed z-30 ${CORNER} ${DISC} cursor-pointer bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-strong)] md:hidden ${FOCUS}`}
      >
        <Plus size={39} weight="light" aria-hidden="true" />
      </button>

      {open
        ? createPortal(
            /* Portalled for the reason ProfileNavPanel is: a non-`none`
               backdrop-filter on an ancestor becomes the containing block for
               `fixed` children, which would trap this against the header box. */
            <div className="md:hidden">
              {/* Pointer-only: keyboard users close with Escape or the close
                  button, so the scrim is not a second announced control. */}
              <div
                data-action-menu-scrim
                aria-hidden="true"
                onClick={() => close(false)}
                className="fixed inset-0 z-40 bg-[rgba(0,0,0,0.25)]"
              />
              <div
                ref={panelRef}
                id={panelId}
                data-action-menu-panel
                className={`fixed z-50 ${CORNER} flex flex-col items-end gap-5`}
              >
                <ul aria-label="Actions" className="flex flex-col gap-5">
                  {ACTION_MENU_ITEMS.map(row)}
                </ul>
                <button
                  type="button"
                  onClick={() => close(true)}
                  aria-label="Close actions"
                  className={`${DISC} cursor-pointer bg-[var(--brand-400)] ${FOCUS}`}
                >
                  <X size={36} weight="regular" aria-hidden="true" />
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

export default ActionMenu;
