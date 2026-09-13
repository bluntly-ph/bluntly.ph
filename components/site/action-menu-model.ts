/**
 * What the floating action menu offers, and what it cannot.
 *
 * Separated from the component so the contract is testable without a DOM, and
 * so the one genuinely surprising entry — a visible action that does nothing —
 * cannot be quietly "fixed" later by someone who assumes it is a bug.
 *
 * "Rate a Seller" is DISABLED IN THE DESIGN. The reference draws its circle in
 * neutral grey, rgb(140,140,140), where the other two are brand orange, and
 * this product has no seller entity to rate: "seller" exists only as a user-role
 * value and a report category. The design is telling a reader the capability
 * exists and is not available yet, so it is shown and disabled rather than
 * hidden — hiding it would lose that message, and enabling it would need a
 * seller model that does not exist.
 */

export type ActionMenuItem = {
  key: string;
  label: string;
  /** Absent when the action cannot be taken. */
  href: string | null;
  enabled: boolean;
};

export const ACTION_MENU_ITEMS: readonly ActionMenuItem[] = [
  { key: "ask", label: "Ask a Question", href: "/questions/new", enabled: true },
  { key: "seller", label: "Rate a Seller", href: null, enabled: false },
  { key: "review", label: "Write a Review", href: "/reviews/new", enabled: true },
] as const;

/** Why a disabled action is unavailable, for assistive technology. */
export const DISABLED_REASON: Record<string, string> = {
  seller: "Rating a seller is not available yet",
};

/** An action is actionable only when it is enabled AND has somewhere to go. */
export function isActionable(item: ActionMenuItem): boolean {
  return item.enabled && typeof item.href === "string" && item.href.length > 0;
}
