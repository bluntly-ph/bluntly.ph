/**
 * The "Let's talk money" card's rules, testable without a DOM.
 *
 * The price a reviewer gives here now feeds the community price panel, and a
 * price observation is an amount AND the marketplace it was paid on. The frame
 * asks for the amount only, so the marketplace question appears once an amount
 * is typed — skipping stays one press, as drawn — and a marketplace picked with
 * no amount is not an observation.
 *
 * The ceiling is the API's (`PriceObservationIn.price`, le=10,000,000).
 */

export const PRICE_PLATFORMS = ["shopee", "lazada", "amazon", "other"] as const;
export type PricePlatform = (typeof PRICE_PLATFORMS)[number];

export const PRICE_PLATFORM_LABEL: Record<PricePlatform, string> = {
  shopee: "Shopee",
  lazada: "Lazada",
  amazon: "Amazon",
  other: "Other",
};

export const MAX_PRICE = 10_000_000;

/** Digits and one decimal point, with at most two decimal places. */
export function normalisePrice(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const dot = cleaned.indexOf(".");
  if (dot === -1) return cleaned;
  const whole = cleaned.slice(0, dot);
  const cents = cleaned.slice(dot + 1).replace(/\./g, "").slice(0, 2);
  return `${whole}.${cents}`;
}

/** Why the card cannot submit yet, or null. A blank amount is a skip. */
export function priceBlocker(price: string, platform: string | null): string | null {
  const trimmed = price.trim();
  if (!trimmed) return null;
  const amount = Number(trimmed);
  if (!Number.isFinite(amount) || amount <= 0) {
    return "Enter the amount you paid, or clear it to skip.";
  }
  if (amount > MAX_PRICE) return "That is more than a price we can record. Check the amount.";
  if (!platform) return "Pick where you bought it.";
  return null;
}

/** The two review fields, sent together or not at all. */
export function pricePayload(
  price: string,
  platform: string | null,
): { price_paid: number | null; price_platform: string | null } {
  const trimmed = price.trim();
  if (!trimmed) return { price_paid: null, price_platform: null };
  const amount = Number(trimmed);
  return { price_paid: Number.isFinite(amount) ? amount : null, price_platform: platform };
}
