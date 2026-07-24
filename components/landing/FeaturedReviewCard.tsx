import Link from "next/link";
import { DotsThree, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

import type { FeaturedData } from "@/lib/reviews";

/**
 * The hero's headline review — the straight white card sitting on a tilted coral
 * card, exactly as drawn (the "stacked papers" look). The backing card is the
 * same box rotated a few degrees so its corners peek out on every side.
 */
export function FeaturedReviewCard({ featured }: { featured: FeaturedData }) {
  return (
    <div className="relative">
      {/* Tilted cards peeking behind. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 rotate-[6deg] rounded-[var(--radius-sm)]"
        style={{ backgroundColor: "rgba(255, 120, 80, 0.22)" }}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 rotate-[3deg] rounded-[var(--radius-sm)]"
        style={{ backgroundColor: "rgba(255, 120, 80, 0.12)" }}
      />

      <Link
        href={featured.id ? `/reviews/${featured.id}` : "/search"}
        className="relative block rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)] outline outline-1 outline-[var(--line-hairline-10)] transition-transform duration-[var(--duration-base)] hover:-translate-y-0.5"
      >
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-8 w-8 shrink-0 rounded-full"
            style={{ background: "hsl(24 60% 58%)" }}
          />
          <span className="truncate text-[14px] font-semibold text-[var(--text-primary)]">
            {featured.author}
          </span>
          <ShieldCheck
            size={16}
            weight="fill"
            className="shrink-0 text-[var(--accent-trust)]"
          />
          <span className="shrink-0 text-[12px] font-medium text-[var(--text-secondary)]">
            {featured.trust}
          </span>
          <span className="shrink-0 text-[12px] text-[var(--text-muted)]">
            · {featured.ageLabel}
          </span>
          <DotsThree size={20} className="ml-auto shrink-0 text-[var(--text-muted)]" />
        </div>

        <h3 className="mt-3 line-clamp-2 text-[15px] font-semibold leading-snug text-[var(--text-primary)]">
          {featured.title}
        </h3>
        <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          {featured.excerpt}
        </p>
      </Link>
    </div>
  );
}

export default FeaturedReviewCard;
