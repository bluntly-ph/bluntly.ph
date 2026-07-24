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
  } | null;
  product: {
    id: string;
    canonical_name: string | null;
    category: string | null;
    avg_rating: string | null;
  } | null;
};

export type ReviewFull = FeedItem;

/** A single review with its author and product, or null if not found/visible. */
export async function getReviewFull(id: string): Promise<ReviewFull | null> {
  try {
    return await apiFetch<FeedItem>(`/api/v1/reviews/${id}/full`);
  } catch {
    return null;
  }
}

export { ageLabel, compact };

export type FeaturedData = {
  id: string;
  author: string;
  trust: string;
  ageLabel: string;
  title: string;
  excerpt: string;
};

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
export function usablePhoto(url: string | null): string | null {
  if (!url || url.includes("example.com")) return null;
  return url.startsWith("http") ? url : null;
}

/** The review's own title, prefixed with the product when we have a name. */
function cardTitle(item: FeedItem): string {
  const product = item.product?.canonical_name?.trim();
  const title = item.review.title.trim();
  return product && !title.toLowerCase().includes(product.toLowerCase())
    ? `${product} — ${title}`
    : title;
}

function toCard(item: FeedItem): ReviewCardData {
  const author = authorName(item);
  return {
    id: item.review.id,
    author,
    authorHue: hueOf(author),
    ageLabel: ageLabel(item.review.created_at),
    title: cardTitle(item),
    upvotes: compact(item.review.helpful_votes),
    comments: "",
    imageHue: hueOf(item.review.id),
    imageUrl: usablePhoto(item.review.photo_url),
  };
}

function toFeatured(item: FeedItem): FeaturedData {
  return {
    id: item.review.id,
    author: authorName(item),
    trust: item.author?.trust_level_name ?? `Stage ${item.author?.trust_stage ?? 0}`,
    ageLabel: ageLabel(item.review.created_at),
    title: cardTitle(item),
    excerpt: item.review.discussion,
  };
}

/** The curated fallback featured card, from the static sample content. */
const SAMPLE_FEATURED: FeaturedData = {
  id: "",
  author: FEATURED_REVIEW.author,
  trust: "Community Expert",
  ageLabel: FEATURED_REVIEW.ageLabel,
  title: FEATURED_REVIEW.title,
  excerpt: FEATURED_REVIEW.excerpt,
};

/** Search / browse results for the search, category, and profile surfaces. */
export async function searchReviews(opts: {
  q?: string;
  category?: string;
  author_id?: string;
  sort?: "wilson" | "newest";
  limit?: number;
}): Promise<ReviewCardData[]> {
  const params = new URLSearchParams({
    sort: opts.sort ?? "wilson",
    limit: String(opts.limit ?? 24),
  });
  if (opts.q?.trim()) params.set("q", opts.q.trim());
  if (opts.category) params.set("category", opts.category);
  if (opts.author_id) params.set("author_id", opts.author_id);
  try {
    const items = await apiFetch<FeedItem[]>(`/api/v1/reviews/feed?${params}`);
    return items.map(toCard);
  } catch {
    return [];
  }
}

export async function getLandingReviews(): Promise<{
  featured: FeaturedData;
  cards: ReviewCardData[];
}> {
  try {
    const items = await apiFetch<FeedItem[]>(
      "/api/v1/reviews/feed?sort=wilson&limit=6",
    );
    if (items?.length) {
      return { featured: toFeatured(items[0]), cards: items.map(toCard) };
    }
  } catch {
    // fall through to the curated samples
  }
  return { featured: SAMPLE_FEATURED, cards: READING_REVIEWS };
}
