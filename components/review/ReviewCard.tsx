import Link from "next/link";
import { ArrowFatUp, ChatCircle, ImageSquare } from "@phosphor-icons/react/dist/ssr";

import type { ReviewCardData } from "@/lib/landing-data";

/**
 * The review card used on the landing rail, search results and category pages —
 * a square cover with the author floated over its top, then title and the
 * upvote / comment counts. The product image is a hue-tinted placeholder until
 * real photos are wired (see lib/landing-data.ts).
 */
export function ReviewCard({
  review,
  className = "",
}: {
  review: ReviewCardData;
  className?: string;
}) {
  return (
    <Link
      href={`/reviews/${review.id}`}
      className={[
        "group flex flex-col overflow-hidden rounded-[var(--radius-sm)]",
        "bg-[var(--surface-card)] shadow-[var(--shadow-card)]",
        "outline outline-1 outline-transparent transition-[outline-color]",
        "duration-[var(--duration-fast)] hover:outline-[var(--line-hairline-10)]",
        "focus-visible:outline-[var(--accent-primary)]",
        className,
      ].join(" ")}
    >
      <div className="relative aspect-square w-full overflow-hidden">
        {review.imageUrl ? (
          // A reviewer's own photo. Plain img so no image-domain config is needed;
          // the feed filters out the synthetic seed URLs.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={review.imageUrl}
            alt=""
            className="absolute inset-0 h-full w-full object-cover transition-transform duration-[var(--duration-base)] group-hover:scale-[1.03]"
          />
        ) : (
          <div
            aria-hidden="true"
            className="absolute inset-0 grid place-items-center transition-transform duration-[var(--duration-base)] group-hover:scale-[1.03]"
            style={{
              background: `linear-gradient(150deg, hsl(${review.imageHue} 42% 74%), hsl(${review.imageHue + 24} 38% 55%))`,
            }}
          >
            <ImageSquare size={30} weight="light" className="text-white/55" />
          </div>
        )}
        {/* Legibility scrim behind the author, as drawn (Rectangle 233). */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-14 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.35),transparent)]"
        />
        <div className="absolute inset-x-0 top-0 flex items-center gap-2 p-3 text-white">
          <span
            aria-hidden="true"
            className="h-6 w-6 shrink-0 rounded-full ring-1 ring-white/40"
            style={{ background: `hsl(${review.authorHue} 55% 55%)` }}
          />
          <span className="text-[12px] font-medium">{review.author}</span>
          <span aria-hidden="true" className="text-white/70">
            ·
          </span>
          <span className="text-[12px] text-white/80">{review.ageLabel}</span>
        </div>
      </div>

      <div className="flex flex-1 flex-col p-3">
        {/* Product bold, then the reviewer's conclusion in normal weight
            (BUG-006) — one undifferentiated block gave no way to tell what was
            reviewed from what was concluded about it. */}
        {review.product ? (
          <p className="line-clamp-1 text-[13px] font-semibold leading-snug text-[var(--text-primary)]">
            {review.product}
          </p>
        ) : null}
        <h3
          className={[
            "line-clamp-3 text-[13px] leading-snug text-[var(--text-secondary)]",
            review.product ? "mt-0.5 font-normal" : "text-[14px] font-semibold text-[var(--text-primary)]",
          ].join(" ")}
        >
          {review.title}
        </h3>
        {/* Count then icon, both stats always present, as drawn. */}
        <div className="mt-3 flex items-center gap-3 text-[12px] text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1">
            {review.upvotes}
            <ArrowFatUp size={14} weight="fill" className="text-[var(--accent-success)]" />
          </span>
          <span className="inline-flex items-center gap-1">
            {review.comments || "0"}
            <ChatCircle size={14} />
          </span>
        </div>
      </div>
    </Link>
  );
}

export default ReviewCard;
