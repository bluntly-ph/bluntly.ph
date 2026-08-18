import "server-only";

import { apiFetch } from "./api/client";
import {
  FEATURED_REVIEW,
  READING_REVIEWS,
  type ReviewCardData,
} from "./landing-data";

/**
 * Read-side data for the public card surfaces, from `GET /api/v1/reviews/feed`
 * (published reviews joined with author + product). Everything is fetched
 * server-side without a token — the feed is public. If the backend is
 * unreachable or empty, the curated landing samples stand in so the page is
 * never blank.
 */

export type Verdict = "yes_absolutely" | "it_depends" | "hard_pass";

type FeedItem = {
  review: {
    id: string;
    review_id: string | null;
    title: string;
    discussion: string;
    verdict: Verdict;
    verdict_explanation: string | null;
    target_audience: string | null;
    anti_target_audience: string | null;
    star_rating: number;
    pros: string[] | null;
    cons: string[] | null;
    price_paid: string | null;
    photo_url: string | null;
    verification_status: "verified" | "unverified";
    helpful_votes: number;
    unhelpful_votes: number;
    /**
     * The requesting viewer's own vote (BUG-013). Only ever populated when the
     * call carries a token — an anonymous read has no viewer, so it is null for
     * everyone and the response stays safely cacheable.
     */
    my_vote: "up" | "down" | null;
    created_at: string;
    referral_redirect_url: string | null;
  };
  author: {
    id: string;
    username: string | null;
    display_name: string | null;
    avatar_url: string | null;
    trust_stage: number;
    trust_level_name: string | null;
    /** 0..100 (ADR-003); shown beside the level name. See lib/trust.ts. */
    reputation_score: string | null;
  } | null;
  product: {
    id: string;
    canonical_name: string | null;
    category: string | null;
    avg_rating: string | null;
    /** The product listing image, behind the reviewer's own photo (BUG-009). */
    image_url: string | null;
  } | null;
  /** Live count of non-removed comments, for the card's stats row (BUG-006). */
  comment_count: number;
};

export type ReviewFull = FeedItem;

/**
 * A single review with its author and product, or null if not found/visible.
 *
 * Pass the viewer's `token` to get `my_vote` populated (BUG-013). Doing so also
 * suppresses the shared Data Cache — apiFetch drops `revalidate` whenever a
 * token is present — which is the point: a response carrying one reader's vote
 * must never be served to another. Signed-out readers keep the cached path.
 */
export async function getReviewFull(
  id: string,
  token?: string | null,
): Promise<ReviewFull | null> {
  try {
    return await apiFetch<FeedItem>(`/api/v1/reviews/${id}/full`, {
      token: token ?? undefined,
      revalidate: 60,
    });
  } catch {
    return null;
  }
}

export { ageLabel, compact };

export type FeaturedData = {
  id: string;
  author: string;
  /** The @handle, shown instead of a "Verified Buyer" label (BUG-004). */
  username: string | null;
  /** The reviewer's own photo, when they have one; else a hue placeholder. */
  avatarUrl: string | null;
  authorHue: number;
  trust: string;
  ageLabel: string;
  /** Trust level name and its 0..100 score, rendered together by TrustBadge. */
  trustStage: number;
  trustScore: string | null;
  /** Bold half of the split headline — the product (BUG-004). */
  product: string | null;
  /** Italic half — what the reviewer concluded about it. */
  title: string;
  excerpt: string;
};

/**
 * Split a headline into "what it is" and "what they thought" (BUG-004).
 *
 * Reviewers overwhelmingly write titles that already name the product —
 * "Akko 5075B Plus — the budget board that punches up" — which is why simply
 * prefixing the canonical name produced "Akko 5075B Plus — Akko 5075B Plus — …".
 * So prefer the reviewer's own dash if there is one, and fall back to the
 * canonical name only when the title carries no product of its own.
 */
export function splitHeadline(
  title: string,
  productName: string | null | undefined,
): { product: string | null; rest: string } {
  const dash = title.match(/^(.{2,80}?)\s+[—–-]\s+(.+)$/);
  if (dash) return { product: dash[1].trim(), rest: dash[2].trim() };
  if (productName?.trim()) return { product: productName.trim(), rest: title.trim() };
  return { product: null, rest: title.trim() };
}

/** Stable 0–359 hue from a string, for placeholder avatar/image tints. */
function hueOf(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) % 360;
  return h;
}

/** "5h" / "12d" / "3w" — the compact age the cards show. */
function ageLabel(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  const h = Math.floor(secs / 3600);
  if (h < 1) return `${Math.max(1, Math.floor(secs / 60))}m`;
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return `${Math.floor(d / 7)}w`;
}

/** 11 → "11", 14800 → "14.8k", 3_200_000 → "3.2m". */
function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
}

function authorName(item: FeedItem): string {
  return item.author?.display_name || item.author?.username || "reviewer";
}

/** A submitted photo we can actually render — not the synthetic seed placeholder. */
export function usablePhoto(url: string | null | undefined): string | null {
  if (!url || url.includes("example.com")) return null;
  return url.startsWith("http") ? url : null;
}

/**
 * The card headline. Reviewers write titles that already name the product
 * ("Akko 5075B Plus — the budget board…"), so we use the title as-is; prefixing
 * the canonical product name only produced "Product — Product — …" duplication.
 */
function cardTitle(item: FeedItem): string {
  return item.review.title.trim();
}

function toCard(item: FeedItem): ReviewCardData {
  const author = authorName(item);
  return {
    id: item.review.id,
    author,
    authorHue: hueOf(author),
    ageLabel: ageLabel(item.review.created_at),
    product: item.product?.canonical_name ?? null,
    title: cardTitle(item),
    upvotes: compact(item.review.helpful_votes),
    // Real, from the feed's grouped count (BUG-006). Hardcoded empty before,
    // which is why the comment stat never once appeared on a card.
    comments: item.comment_count ? compact(item.comment_count) : "0",
    imageHue: hueOf(item.review.id),
    // The reviewer's own photo first — it is evidence they actually held the
    // thing. The product listing image is the fallback (BUG-009); the hue
    // placeholder is the last resort, not the default it had become.
    imageUrl:
      usablePhoto(item.review.photo_url) ?? usablePhoto(item.product?.image_url),
  };
}

function toFeatured(item: FeedItem): FeaturedData {
  const author = authorName(item);
  // The canonical name in full — the card used to shorten it, so "Jisulife
  // Handheld Fan Life9" reached the reader as "Jisulife Life9" (BUG-004).
  const { product, rest } = splitHeadline(cardTitle(item), item.product?.canonical_name);
  return {
    id: item.review.id,
    author,
    username: item.author?.username ?? null,
    avatarUrl: usablePhoto(item.author?.avatar_url),
    authorHue: hueOf(author),
    trust: item.author?.trust_level_name ?? `Stage ${item.author?.trust_stage ?? 0}`,
    trustStage: item.author?.trust_stage ?? 0,
    trustScore: item.author?.reputation_score ?? null,
    ageLabel: ageLabel(item.review.created_at),
    product,
    title: rest,
    excerpt: item.review.discussion,
  };
}

/** The curated fallback featured card, from the static sample content. */
const SAMPLE_HEADLINE = splitHeadline(FEATURED_REVIEW.title, null);

const SAMPLE_FEATURED: FeaturedData = {
  id: "",
  author: FEATURED_REVIEW.author,
  // No handle or photo for the sample: it stands in when the backend is
  // unreachable, and inventing a plausible @handle for a person who does not
  // exist is worse than showing the display name alone.
  username: null,
  avatarUrl: null,
  authorHue: hueOf(FEATURED_REVIEW.author),
  trust: "Community Expert",
  // No score on the sample: it stands in when the backend is unreachable, and a
  // fabricated trust number is exactly the kind of thing this site exists to
  // not do. TrustBadge renders the level name alone when the score is null.
  trustStage: 3,
  trustScore: null,
  ageLabel: FEATURED_REVIEW.ageLabel,
  product: SAMPLE_HEADLINE.product,
  title: SAMPLE_HEADLINE.rest,
  excerpt: FEATURED_REVIEW.excerpt,
};

/** Search / browse results for the search, category, and profile surfaces. */
export async function searchReviews(opts: {
  q?: string;
  category?: string;
  author_id?: string;
  sort?: "wilson" | "newest";
  limit?: number;
}): Promise<ReviewCardData[] | null> {
  const params = new URLSearchParams({
    sort: opts.sort ?? "wilson",
    limit: String(opts.limit ?? 24),
  });
  if (opts.q?.trim()) params.set("q", opts.q.trim());
  if (opts.category) params.set("category", opts.category);
  if (opts.author_id) params.set("author_id", opts.author_id);
  try {
    const items = await apiFetch<FeedItem[]>(`/api/v1/reviews/feed?${params}`, {
      revalidate: 60,
    });
    return items.map(toCard);
  } catch {
    // null, not [] — "we could not reach the server" and "this search matched
    // nothing" are different answers, and only one of them is the reader's
    // fault to act on. Returning [] made an outage read as "No reviews found".
    return null;
  }
}

export type AuthorProfile = {
  id: string;
  name: string;
  username: string | null;
  avatarUrl: string | null;
  trust: string;
  trustStage: number;
  /** 0..100 (ADR-003), shown beside the level name. See lib/trust.ts. */
  trustScore: string | null;
};

/**
 * A public reviewer profile: the author's public identity plus their published
 * reviews. Built from the same public feed (filtered by `author_id`), so no
 * privileged endpoint is needed — the author block on their own reviews carries
 * everything the header shows. Returns null when the reviewer has nothing public.
 */
export async function getAuthorProfile(authorId: string): Promise<{
  author: AuthorProfile;
  cards: ReviewCardData[];
} | null> {
  try {
    const items = await apiFetch<FeedItem[]>(
      `/api/v1/reviews/feed?author_id=${encodeURIComponent(authorId)}&sort=newest&limit=48`,
      { revalidate: 60 },
    );
    const a = items?.[0]?.author;
    if (!a) return null;
    return {
      author: {
        id: a.id,
        name: a.display_name || a.username || "reviewer",
        username: a.username,
        avatarUrl: a.avatar_url,
        trust: a.trust_level_name ?? `Stage ${a.trust_stage}`,
        trustStage: a.trust_stage,
        trustScore: a.reputation_score ?? null,
      },
      cards: items.map(toCard),
    };
  } catch {
    return null;
  }
}

export async function getLandingReviews(): Promise<{
  featured: FeaturedData;
  cards: ReviewCardData[];
}> {
  try {
    const items = await apiFetch<FeedItem[]>(
      "/api/v1/reviews/feed?sort=wilson&limit=6",
      { revalidate: 60 },
    );
    if (items?.length) {
      return { featured: toFeatured(items[0]), cards: items.map(toCard) };
    }
  } catch {
    // fall through to the curated samples
  }
  return { featured: SAMPLE_FEATURED, cards: READING_REVIEWS };
}
