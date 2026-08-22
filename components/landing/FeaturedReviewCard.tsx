import Image from "next/image";
import Link from "next/link";
import { DotsThree } from "@phosphor-icons/react/dist/ssr";

import { TrustBadge } from "@/components/ui/TrustBadge";
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
      {/* The stack, exactly as drawn on Page 1: two tinted cards in brand
          orange at 10% — one rotated +5deg, one square behind — with the real
          card counter-rotated -5deg on top. The tint is a flat
          rgba(239,88,33,0.1) in the frame, not a shadow: the depth comes from
          the rotation, which is why softening it into shadows (as this
          previously did) flattened the whole effect. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 rotate-[5deg] rounded-[12px]"
        style={{ backgroundColor: "rgba(239, 88, 33, 0.1)" }}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 rounded-[12px]"
        style={{ backgroundColor: "rgba(239, 88, 33, 0.1)" }}
      />

      <Link
        href={featured.id ? `/reviews/${featured.id}` : "/search"}
        // -5deg and the frame's own shadow colour (#bcaca6 — a warm grey, not
        // black). Hover lifts the rotation slightly rather than translating,
        // so the card stays seated in its stack.
        className="relative block -rotate-[5deg] rounded-[12px] bg-[var(--surface-app)] p-4 shadow-[0px_4px_4px_0px_#bcaca6] transition-transform duration-[var(--duration-base)] hover:-rotate-[3deg]"
      >
        <div className="flex items-start gap-2">
          {featured.avatarUrl ? (
            // The reviewer's real photo (BUG-004) — the card showed a flat
            // colour disc, which reads as a missing person rather than a person.
            <Image
              src={featured.avatarUrl}
              alt=""
              width={32}
              height={32}
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
              <TrustBadge
                levelName={featured.trust}
                stage={featured.trustStage}
                score={featured.trustScore}
                plain
              />
            </div>
            <span className="block text-[12px] text-[var(--text-muted)] sm:mt-0.5">
              {featured.ageLabel}
            </span>
          </div>

          <DotsThree size={20} className="mt-0.5 shrink-0 text-[var(--text-muted)]" />
        </div>

        {/* Product bold, verdict italic, split on the dash reviewers already
            write (BUG-004). */}
        {/* h2, not h3: this card sits directly under the page h1 in the hero,
            so h3 skipped a level — a screen reader user navigating by heading
            hears the outline jump. The grid cards below stay h3 because they
            sit under the "What people are reading" h2. */}
        <h2 className="mt-3 line-clamp-3 text-[15px] leading-snug text-[var(--text-primary)]">
          {featured.product ? (
            <>
              <span className="font-semibold">{featured.product}</span>
              <span className="text-[var(--text-muted)]"> — </span>
              <span className="italic text-[var(--text-secondary)]">{featured.title}</span>
            </>
          ) : (
            <span className="font-semibold">{featured.title}</span>
          )}
        </h2>
        <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          {featured.excerpt}
        </p>
      </Link>
    </div>
  );
}

export default FeaturedReviewCard;
