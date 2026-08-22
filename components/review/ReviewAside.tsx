import Image from "next/image";
import Link from "next/link";
import { SealCheck, ShoppingBag, Star } from "@phosphor-icons/react/dist/ssr";

import { PricePanel } from "@/components/product/PricePanel";
import { TrustBadge } from "@/components/ui/TrustBadge";
import type { ReviewCardData } from "@/lib/landing-data";
import type { PricePanel as PanelData } from "@/lib/products";
import { type ReviewFull, usablePhoto } from "@/lib/reviews";

/**
 * The desktop context column for a review.
 *
 * Only rendered at `lg` and up. At narrower widths the same information already
 * appears in the reading column in the order the mobile frame puts it, so this
 * is additive to desktop rather than a second copy of the page.
 *
 * Everything here comes from data the page already holds — `FeedProduct` gives
 * the name, category, rating and image; the price panel and related reviews are
 * fetched by the page. Nothing is invented to fill the column, which is why
 * blocks disappear rather than showing placeholder text when their data is
 * absent.
 */
export function ReviewAside({
  data,
  panel,
  related,
}: {
  data: ReviewFull;
  panel: PanelData | null;
  related: ReviewCardData[];
}) {
  const { review, author, product } = data;
  const authorName = author?.display_name || author?.username || "reviewer";
  const productImage = usablePhoto(product?.image_url);

  return (
    <div className="flex flex-col gap-8">
      {product ? (
        <section aria-labelledby="aside-product">
          <h2 id="aside-product" className={LABEL}>
            The product
          </h2>

          <div className="mt-3 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-card)] shadow-[var(--shadow-hairline-inset)]">
            {productImage ? (
              // The context column is a fixed 20rem, so the intrinsic box is
              // known exactly.
              <div className="relative aspect-[4/3] w-full">
                <Image
                  src={productImage}
                  alt=""
                  fill
                  sizes="30rem"
                  className="object-cover"
                />
              </div>
            ) : (
              <div
                aria-hidden="true"
                className="grid aspect-[4/3] w-full place-items-center"
                style={{
                  background:
                    "linear-gradient(150deg, hsl(20 42% 78%), hsl(30 38% 62%))",
                }}
              >
                <ShoppingBag size={30} weight="light" className="text-white/60" />
              </div>
            )}

            <div className="p-4">
              {product.canonical_name ? (
                <p className="text-[14px] font-semibold leading-snug text-[var(--text-primary)]">
                  {product.canonical_name}
                </p>
              ) : null}

              <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-muted)]">
                {product.category ? (
                  <Link
                    href={`/search?category=${encodeURIComponent(product.category)}`}
                    className="rounded-[var(--radius-md)] px-2 py-0.5 capitalize text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--accent-primary)]"
                  >
                    {product.category}
                  </Link>
                ) : null}
                {product.review_count > 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <Star
                      size={13}
                      weight="fill"
                      className="text-[var(--accent-star)]"
                    />
                    {product.avg_rating} · {product.review_count}{" "}
                    {product.review_count === 1 ? "review" : "reviews"}
                  </span>
                ) : null}
              </div>

              {/* The commercial action lives here on desktop; the reading column
                  hides its own copy at `lg` so the page has one Buy control. */}
              {review.referral_redirect_url ? (
                <a
                  href={review.referral_redirect_url}
                  target="_blank"
                  rel="noopener noreferrer nofollow sponsored"
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[var(--accent-primary-strong)]"
                >
                  <ShoppingBag size={16} weight="fill" />
                  Buy it here
                </a>
              ) : (
                <span
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] px-4 py-2.5 text-[13px] font-semibold text-[var(--text-muted)] shadow-[var(--shadow-hairline-inset)]"
                  title="An affiliate link is added once a moderator approves this review."
                >
                  <ShoppingBag size={16} />
                  Buy link pending
                </span>
              )}

              {review.price_paid ? (
                <p className="mt-3 text-[12px] text-[var(--text-secondary)]">
                  Reviewer paid{" "}
                  <span className="font-semibold text-[var(--text-primary)]">
                    ₱{review.price_paid}
                  </span>
                </p>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {/* FR-2. The panel publishes nothing below three independent submitters
          and says so itself, so it is safe to render unconditionally. It brings
          its own heading, so it is not wrapped in another one. */}
      <PricePanel panel={panel} compact />

      {author ? (
        <section aria-labelledby="aside-reviewer">
          <h2 id="aside-reviewer" className={LABEL}>
            The reviewer
          </h2>
          <div className="mt-3 flex items-center gap-3">
            <span
              aria-hidden="true"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-[14px] font-semibold text-white"
              style={{ background: "hsl(24 55% 55%)" }}
            >
              {authorName.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0">
              <Link
                href={`/u/${author.id}`}
                className="block truncate text-[14px] font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
              >
                {author.username ? `@${author.username}` : authorName}
              </Link>
              <TrustBadge
                levelName={author.trust_level_name}
                stage={author.trust_stage}
                score={author.reputation_score}
                plain
              />
            </div>
          </div>

          {review.verification_status === "verified" ? (
            <p className="mt-3 inline-flex items-center gap-1.5 text-[12px] text-[var(--accent-success)]">
              <SealCheck size={14} weight="fill" />
              Proof of purchase provided
            </p>
          ) : null}

          <Link
            href={`/u/${author.id}`}
            className="mt-3 block text-[13px] font-semibold text-[var(--accent-primary)] hover:underline"
          >
            More from this reviewer →
          </Link>
        </section>
      ) : null}

      {related.length > 0 ? (
        <section aria-labelledby="aside-related">
          <h2 id="aside-related" className={LABEL}>
            Related reviews
          </h2>
          <ul className="mt-3 flex flex-col">
            {related.map((item) => (
              <li
                key={item.id}
                className="border-b border-[var(--border-subtle)] last:border-0"
              >
                <Link
                  href={`/reviews/${item.id}`}
                  className="group flex gap-3 py-3 hover:bg-[var(--line-hairline-10)]"
                >
                  {/* A 48px thumbnail. This was a CSS `background-image`,
                      which no optimizer can reach: the browser fetched the
                      stored photograph at full size for a box this big, and on
                      a review with three related items that came to 1.1 MB —
                      one of them an 887 KB PNG. As an <Image> it is fetched at
                      the size it is drawn. The gradient fallback stays a
                      background, because there is no image to optimize. */}
                  {item.imageUrl ? (
                    <span
                      aria-hidden="true"
                      className="relative block h-12 w-12 shrink-0 overflow-hidden rounded-[var(--radius-sm)]"
                    >
                      <Image
                        src={item.imageUrl}
                        alt=""
                        fill
                        sizes="96px"
                        className="object-cover"
                      />
                    </span>
                  ) : (
                    <span
                      aria-hidden="true"
                      className="h-12 w-12 shrink-0 rounded-[var(--radius-sm)]"
                      style={{
                        background: `linear-gradient(150deg, hsl(${item.imageHue} 42% 78%), hsl(${item.imageHue} 38% 62%))`,
                      }}
                    />
                  )}
                  <span className="min-w-0">
                    {item.product ? (
                      <span className="block truncate text-[12px] text-[var(--text-muted)]">
                        {item.product}
                      </span>
                    ) : null}
                    <span className="block text-[13px] font-medium leading-snug text-[var(--text-primary)] group-hover:text-[var(--accent-primary)]">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-[12px] text-[var(--text-muted)]">
                      {item.upvotes} helpful · {item.ageLabel}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

/**
 * Sidebar block headings.
 *
 * Deliberately smaller and quieter than the reading column's 16px section
 * titles: this column is context, and matching the body's heading weight would
 * make the two compete for the same rung of the hierarchy.
 */
const LABEL =
  "text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]";

export default ReviewAside;
