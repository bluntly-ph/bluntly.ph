/**
 * What the floating action menu offers.
 *
 * Separated from the component so the contract is testable without a DOM.
 *
 * "Rate a Seller" shipped DISABLED for as long as this product had no seller
 * entity: the design drew it in neutral grey, and enabling it would have meant
 * a route with nothing behind it. The completion contract reinstated sellers —
 * stores, moderated claims and seller reviews (migrations 0042, 0043) — so it
 * now opens the seller composer at /sellers/rate.
 *
 * The rule that made the disabled state honest still holds and is tested: an
 * item is actionable only when it is enabled AND has somewhere to go.
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
  { key: "seller", label: "Rate a Seller", href: "/sellers/rate", enabled: true },
  { key: "review", label: "Write a Review", href: "/reviews/new", enabled: true },
] as const;

/**
 * The menu as offered on a given page. On a store's page ("Seller Page -
 * Review" draws the menu there, 4797:16411) "Rate a Seller" carries that store,
 * so the composer opens on its rating step instead of asking which store again;
 * /sellers/rate still resolves the id against the API before using it. The
 * other two actions are about products and are unchanged.
 */
export function actionMenuItems(context: { sellerId?: string } = {}): readonly ActionMenuItem[] {
  const sellerId = context.sellerId?.trim();
  if (!sellerId) return ACTION_MENU_ITEMS;
  return ACTION_MENU_ITEMS.map((item) =>
    item.key === "seller" ? { ...item, href: `/sellers/rate?seller=${encodeURIComponent(sellerId)}` } : item,
  );
}

/** Why a disabled action is unavailable, for assistive technology. */
export const DISABLED_REASON: Record<string, string> = {};

/** An action is actionable only when it is enabled AND has somewhere to go. */
export function isActionable(item: ActionMenuItem): boolean {
  return item.enabled && typeof item.href === "string" && item.href.length > 0;
}
