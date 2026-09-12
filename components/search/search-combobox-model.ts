/**
 * Keyboard semantics for the search combobox, as data.
 *
 * Extracted so the contract is testable: this project has no DOM test
 * environment, and the defect this module exists to prevent was invisible to
 * TypeScript and ESLint alike.
 *
 * The defect: `<input type="search">` clears itself when Escape is pressed —
 * a browser default, not anything the component did. The handler dismissed the
 * suggestion list but never suppressed that default, so the query disappeared
 * too, which contradicted the component's own documented intent and left
 * nothing for ArrowDown to reopen. Production QA caught it; the types could
 * not, because a missing `preventDefault()` is not a type error.
 */

export type ComboKeyState = {
  /** The suggestion list is on screen. */
  open: boolean;
  /** The reader closed the list without changing the query. */
  dismissed: boolean;
  /** The query is long enough to search for. */
  eligible: boolean;
  /** How many suggestions are currently held. */
  itemCount: number;
  /** Index of the highlighted suggestion, or -1. */
  active: number;
};

export type ComboKeyAction =
  /** Nothing to do — let the key through untouched. */
  | { type: "none"; preventDefault: false }
  /** Close the list. */
  | { type: "dismiss"; preventDefault: boolean }
  /** Put the list back on screen, highlighting `to` when there is one to highlight. */
  | { type: "reopen"; to: number | null; preventDefault: boolean }
  /** Move the highlight to this index. */
  | { type: "move"; to: number; preventDefault: true }
  /** Accept the suggestion at this index. */
  | { type: "choose"; index: number; preventDefault: true };

// Frozen because it is a single instance handed to every caller that needs it.
const NONE: ComboKeyAction = Object.freeze({ type: "none", preventDefault: false });

export function comboKeyAction(key: string, state: ComboKeyState): ComboKeyAction {
  if (key === "Escape") {
    // Suppress the native clear only while the list is open: the first Escape
    // closes the suggestions and keeps the query, which is what the ARIA
    // combobox pattern specifies. A second Escape then falls through to the
    // browser's own clear, which is a useful affordance in its own right.
    return { type: "dismiss", preventDefault: state.open };
  }

  if (!state.open) {
    // ArrowDown is the standard way back into a dismissed list, so it must not
    // be swallowed by the closed guard.
    //
    // It also highlights the first option, which the ARIA combobox pattern
    // specifies: "if the listbox is not displayed, displays the listbox and
    // moves visual focus to the first option". Reopening without a highlight
    // made ArrowDown a two-press affair — one to reveal the list, another to
    // enter it — and left `aria-activedescendant` empty on a visible list,
    // which tells a screen reader nothing is current.
    if (key === "ArrowDown" && state.itemCount === 0 && state.eligible) {
      // Nothing fetched yet for this query, so there is nothing to highlight.
      return { type: "reopen", to: null, preventDefault: false };
    }
    if (key === "ArrowDown" && state.dismissed) {
      return { type: "reopen", to: state.itemCount > 0 ? 0 : null, preventDefault: true };
    }
    return NONE;
  }

  // `open` implies at least one item, so the wrap-around arithmetic is safe.
  if (key === "ArrowDown") {
    return {
      type: "move",
      to: state.active < 0 ? 0 : (state.active + 1) % state.itemCount,
      preventDefault: true,
    };
  }
  if (key === "ArrowUp") {
    return {
      type: "move",
      to: state.active <= 0 ? state.itemCount - 1 : state.active - 1,
      preventDefault: true,
    };
  }
  // Only intercept Enter when a suggestion is highlighted; otherwise the form
  // submits and searches exactly what was typed.
  if (key === "Enter" && state.active >= 0) {
    return { type: "choose", index: state.active, preventDefault: true };
  }
  return NONE;
}
