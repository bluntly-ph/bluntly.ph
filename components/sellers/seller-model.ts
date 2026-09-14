/**
 * The rules behind the seller surfaces (FR-4), testable without a DOM.
 *
 * Two of them carry the honesty of every seller page:
 *
 *  - A store nobody has rated shows NO rate, not "0%". The API sends null for
 *    every rate and average until there is a review to aggregate, and
 *    `percent(null)` keeps it null rather than formatting it into a claim.
 *  - A rating is sent only once all six answers exist. "Not the same",
 *    "Missing item" and "I don't recommend" are answers; `false` is not blank.
 *
 * Limits: the title cap and the prose floor are read off the owner's frames
 * ("0/30 characters", "15 characters remaining"); the API allows a 200
 * character title, the same split product reviews use.
 */

export const MAX_SELLER_TITLE = 30;
export const MIN_SELLER_PROSE = 15;
export const MAX_SELLER_PHOTOS = 4;
export const MAX_SELLER_COMMENT = 2000;

export type SellerPlatform = "shopee" | "lazada" | "amazon" | "other";

export const PLATFORM_LABEL: Record<SellerPlatform, string> = {
  shopee: "Shopee",
  lazada: "Lazada",
  amazon: "Amazon",
  other: "Other marketplace",
};

export type SellerDraft = {
  overall: number | null;
  recommend: boolean | null;
  service: number | null;
  packaging: number | null;
  accuracy: boolean | null;
  completeness: boolean | null;
  title: string;
  comment: string;
  photoUrls: string[];
};

export type SellerDimension =
  | "overall"
  | "recommend"
  | "service"
  | "packaging"
  | "accuracy"
  | "completeness";

/** Top to bottom, as "Seller Review - Step 2.png" draws them. */
const DIMENSION_ORDER: readonly SellerDimension[] = [
  "overall",
  "recommend",
  "service",
  "packaging",
  "accuracy",
  "completeness",
];

/** What a disabled Continue is waiting for, said to assistive technology. */
export const DIMENSION_PROMPT: Record<SellerDimension, string> = {
  overall: "Give the seller a star rating",
  recommend: "Say whether you recommend this seller",
  service: "Rate their customer service",
  packaging: "Rate their packaging",
  accuracy: "Say whether the order matched the listing",
  completeness: "Say whether your order was complete",
};

export function emptySellerDraft(): SellerDraft {
  return {
    overall: null,
    recommend: null,
    service: null,
    packaging: null,
    accuracy: null,
    completeness: null,
    title: "",
    comment: "",
    photoUrls: [],
  };
}

/** The first unanswered dimension, or null when all six have an answer. */
export function missingDimension(draft: SellerDraft): SellerDimension | null {
  return DIMENSION_ORDER.find((key) => draft[key] === null) ?? null;
}

/** Why the written step cannot be submitted yet, or null. */
export function contentBlocker(draft: SellerDraft): string | null {
  const title = draft.title.trim();
  if (!title) return "Give your review a title";
  if (title.length > MAX_SELLER_TITLE) {
    return `Keep the title to ${MAX_SELLER_TITLE} characters`;
  }
  const short = MIN_SELLER_PROSE - draft.comment.trim().length;
  if (short > 0) return `${short} more character${short === 1 ? "" : "s"} to go`;
  return null;
}

export type SellerReviewPayload = {
  overall_rating: number;
  would_recommend: boolean;
  customer_service: number;
  packaging_quality: number;
  accuracy: boolean;
  order_completeness: boolean;
  title: string;
  comment: string;
  photo_urls: string[];
};

/** The POST body. Throws rather than sending a half-answered rating. */
export function toSellerReviewPayload(draft: SellerDraft): SellerReviewPayload {
  const missing = missingDimension(draft);
  if (missing) throw new Error(`The ${missing} answer is missing`);
  const blocker = contentBlocker(draft);
  if (blocker) throw new Error(blocker);
  return {
    overall_rating: draft.overall as number,
    would_recommend: draft.recommend as boolean,
    customer_service: draft.service as number,
    packaging_quality: draft.packaging as number,
    accuracy: draft.accuracy as boolean,
    order_completeness: draft.completeness as boolean,
    title: draft.title.trim(),
    comment: draft.comment.trim(),
    photo_urls: [...draft.photoUrls],
  };
}

/** 0.755 -> "76%". Null stays null: no data is not a zero. */
export function percent(rate: number | null): string | null {
  return rate === null ? null : `${Math.round(rate * 100)}%`;
}

export type StarBar = { star: number; count: number; share: number };

/**
 * The five-to-one breakdown. JSON delivers the keys as strings, and a star
 * nobody gave may be absent; both read as a count.
 */
export function distributionBars(distribution: Record<string, number>): StarBar[] {
  const counts = [5, 4, 3, 2, 1].map((star) => ({
    star,
    count: Number(distribution[star] ?? 0) || 0,
  }));
  const total = counts.reduce((sum, bar) => sum + bar.count, 0);
  return counts.map((bar) => ({ ...bar, share: total === 0 ? 0 : bar.count / total }));
}

/** The word under the average ("4.7 Excellent" in the seller page frame). */
export function ratingWord(average: number | null): string | null {
  if (average === null) return null;
  if (average >= 4.5) return "Excellent";
  if (average >= 3.5) return "Good";
  if (average >= 2.5) return "Average";
  if (average >= 1.5) return "Poor";
  return "Bad";
}

/** A store has no logo in this product, so it is drawn as its initials. */
export function sellerInitials(name: string): string {
  const initials = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 3)
    .map((word) => word[0].toUpperCase())
    .join("");
  return initials || "?";
}

/** The line in the card above the written step, following the stars given. */
export function ratingPrompt(overall: number | null): string | null {
  if (overall === null) return null;
  if (overall >= 5) return "You gave them a great rating. We’d love to hear more!";
  if (overall === 4) return "You gave them a pretty good rating. We’d love to hear more!";
  if (overall === 3) return "A mixed experience? Tell people what went right and what didn’t.";
  return "Sorry it didn’t go well. Tell people what happened.";
}

/* --------------------------------------------------- owner dashboard */

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09" -> "Sep 2026". Fixed English names, so the label never depends on locale. */
export function monthLabel(key: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(key);
  if (!match) return key;
  const index = Number(match[2]) - 1;
  return index >= 0 && index < 12 ? `${MONTH_NAMES[index]} ${match[1]}` : key;
}

export type VolumeBar = { month: string; count: number; share: number };

/**
 * Review volume as bars, each a share of the busiest month in the window. The
 * API zero-fills the months, so a quiet month is an empty bar, never a gap.
 */
export function volumeBars(months: { month: string; count: number }[]): VolumeBar[] {
  const max = months.reduce((most, m) => Math.max(most, m.count), 0);
  return months.map((m) => ({ month: m.month, count: m.count, share: max === 0 ? 0 : m.count / max }));
}
