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

/* ------------------------------------------------ report what you paid */

/** The API's variant limit (`PriceObservationIn.variant`, max_length=120). */
export const MAX_VARIANT = 120;

export type ObservationFields = {
  price: string;
  platform: string | null;
  /** YYYY-MM-DD, as an `<input type="date">` gives it. */
  observedAt: string;
  variant: string;
};

/**
 * Today in Manila as YYYY-MM-DD. The API rejects a date after the Philippine
 * today, and UTC is still yesterday for the first eight hours of a Manila day.
 */
export function manilaToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

/**
 * Why a standalone price report cannot be sent yet, or null. Unlike the
 * composer's card nothing is optional here except the variant: the form's
 * only purpose is to file an observation.
 */
export function observationBlocker(fields: ObservationFields, today: string): string | null {
  const trimmed = fields.price.trim();
  const amount = Number(trimmed);
  if (!trimmed || !Number.isFinite(amount) || amount <= 0) return "Enter the amount you paid.";
  if (amount > MAX_PRICE) return "That is more than a price we can record. Check the amount.";
  if (!fields.platform) return "Pick where you bought it.";
  if (!fields.observedAt) return "Pick the date you paid.";
  // ISO dates compare correctly as strings.
  if (fields.observedAt > today) return "That date is in the future.";
  if (fields.variant.trim().length > MAX_VARIANT) {
    return `Keep the variant to ${MAX_VARIANT} characters.`;
  }
  return null;
}

/** The POST /products/{id}/prices body. The price stays a decimal string. */
export function observationPayload(fields: ObservationFields): {
  platform: string | null;
  price: string;
  observed_at: string;
  variant: string | null;
} {
  return {
    platform: fields.platform,
    price: fields.price.trim(),
    observed_at: fields.observedAt,
    variant: fields.variant.trim() || null,
  };
}
