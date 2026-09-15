"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PencilLine, QuestionMark, Star } from "@phosphor-icons/react";
import type { Icon, IconWeight } from "@phosphor-icons/react";

import {
  DISABLED_REASON,
  actionMenuItems,
  isActionable,
  type ActionMenuItem,
} from "@/components/site/action-menu-model";

/**
 * The floating action menu from "Action Menu.png" — phones only.
 *
 * MOUNTED ONLY WHERE THE FIGMA FILE DRAWS IT (lso4Ri4hDaZxvCebhUqlY5, read
 * 2026-09-14): /search, where instance 7224:4943 sits exactly on "Mobile Search
 * Page for Reviewers" (3481:1894), and /sellers/[id], whose frames contain it
 * (4797:16411 in "Seller Page - Review", 4797:16440 / 4797:16469 in "Seller Page
 * - Questions"). The "Question Page" frames also carry it, but that product page
 * has no route. No other screen in the file has it, so home, feed, categories,
 * the questions index and review pages do not mount it. Hidden from `md` (768px)
 * up: every frame that draws it is a 390px phone frame.
 *
 * Measured from the frame at 390x844 (.bluntly-autopilot/figma-reference/
 * ACTION-MENU.md):
 *   collapsed  60x60 disc in --brand-600, 32px from the right and bottom edges,
 *              a 24.75px plus in a 3px round-capped stroke, --shadow-fab
 *              (the disc artwork's 5px drop with a 4px blur)
 *   expanded   black scrim at 25%; action discs on an 80px pitch (20px gaps)
 *              with the close disc, in --brand-400, taking the FAB's place;
 *              label pills 40px tall, 12px radius, --surface-app, 12px from
 *              their disc, 16px type with an 11px cap height, 16px in and
 *              6px out (151 / 131 / 149 wide); glyphs in --surface-app: a
 *              bare question mark, a star, Phosphor PencilLine
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
  review: { icon: PencilLine, size: 28, weight: "regular" },
};

/** The frame's 32px corner, kept clear of a notch or home indicator. */
const CORNER =
  "bottom-[calc(32px_+_env(safe-area-inset-bottom))] right-[calc(32px_+_env(safe-area-inset-right))]";

const DISC =
  "grid h-[60px] w-[60px] shrink-0 place-items-center rounded-full text-[var(--surface-app)] shadow-[var(--shadow-fab)]";

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

/**
 * The plus and close marks exactly as the Figma disc artwork draws them (Action
 * Menu 4417:751, exported 2026-09-14): 3px round-capped strokes in a 36px box —
 * a 24.75px plus, and an X reaching 8.75px from centre. Phosphor's Plus and X
 * are longer and thinner at any weight that exists.
 */
function PlusGlyph() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <path d="M5.625 18h24.75M18 5.625v24.75" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <path d="M9.25 26.75l17.5-17.5M9.25 9.25l17.5 17.5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function ActionMenu({ sellerId }: { sellerId?: string } = {}) {
  const [open, setOpen] = useState(false);
  const items = actionMenuItems({ sellerId });
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
          className={`flex h-10 items-center rounded-[var(--radius-sm)] bg-[var(--surface-app)] pl-4 pr-[6px] text-[16px] tracking-[0.05em] ${
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
        <PlusGlyph />
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
                  {items.map(row)}
                </ul>
                <button
                  type="button"
                  onClick={() => close(true)}
                  aria-label="Close actions"
                  className={`${DISC} cursor-pointer bg-[var(--brand-400)] ${FOCUS}`}
                >
                  <CloseGlyph />
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
