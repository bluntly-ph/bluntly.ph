import Link from "next/link";
import { DotsThree, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

import type { FeaturedData } from "@/lib/reviews";

/**
 * The hero's headline review — the straight white card sitting on tilted coral
 * cards, the "stacked papers" look from the frame.
 *
 * The stack's falloff is deliberate (BUG-004): each layer steps down in both
 * rotation and opacity, and carries a soft shadow of its own, so the edges fade
 * out rather than ending on the hard line that flat tinted rectangles produced.
 */
export function FeaturedReviewCard({ featured }: { featured: FeaturedData }) {
  return (
    <div className="relative">
      {/* Tilted cards peeking behind, back to front. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 rotate-[6deg] rounded-[var(--radius-sm)] shadow-[0_10px_30px_-12px_rgba(32,32,32,0.18)]"
        style={{ backgroundColor: "rgba(255, 120, 80, 0.16)" }}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 rotate-[3deg] rounded-[var(--radius-sm)] shadow-[0_8px_24px_-14px_rgba(32,32,32,0.14)]"
        style={{ backgroundColor: "rgba(255, 120, 80, 0.09)" }}
      />

      <Link
        href={featured.id ? `/reviews/${featured.id}` : "/search"}
        className="relative block rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)] outline outline-1 outline-[var(--line-hairline-10)] transition-transform duration-[var(--duration-base)] hover:-translate-y-0.5"
      >
        <div className="flex items-start gap-2">
          {featured.avatarUrl ? (
            // The reviewer's real photo (BUG-004) — the card showed a flat
            // colour disc, which reads as a missing person rather than a person.
            // Plain img: the avatar host isn't in the next/image allowlist.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={featured.avatarUrl}
              alt=""
              className="h-8 w-8 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span
              aria-hidden="true"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-[12px] font-semibold text-white"
              style={{ background: `hsl(${featured.authorHue} 55% 55%)` }}
            >
              {featured.author.slice(0, 1).toUpperCase()}
            </span>
          )}

          {/* Handle and trust on one line, timestamp stacked beneath it — on a
              phone all four competed for one row and the date won by wrapping. */}
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="truncate text-[14px] font-semibold text-[var(--text-primary)]">
                {featured.username ? `@${featured.username}` : featured.author}
              </span>
              <ShieldCheck
                size={16}
                weight="fill"
                className="shrink-0 text-[var(--accent-trust)]"
              />
              <span className="shrink-0 text-[12px] font-medium text-[var(--accent-trust)]">
                {featured.trust}
              </span>
            </div>
            <span className="block text-[12px] text-[var(--text-muted)] sm:mt-0.5">
              {featured.ageLabel}
            </span>
          </div>

          <DotsThree size={20} className="mt-0.5 shrink-0 text-[var(--text-muted)]" />
        </div>

        {/* Product bold, verdict italic, split on the dash reviewers already
            write (BUG-004). */}
        <h3 className="mt-3 line-clamp-3 text-[15px] leading-snug text-[var(--text-primary)]">
          {featured.product ? (
            <>
              <span className="font-semibold">{featured.product}</span>
              <span className="text-[var(--text-muted)]"> — </span>
              <span className="italic text-[var(--text-secondary)]">{featured.title}</span>
            </>
          ) : (
            <span className="font-semibold">{featured.title}</span>
          )}
        </h3>
        <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          {featured.excerpt}
        </p>
      </Link>
    </div>
  );
}

export default FeaturedReviewCard;
