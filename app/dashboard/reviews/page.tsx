import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ImageSquare } from "@phosphor-icons/react/dist/ssr";

import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { requireOnboardedUser } from "@/lib/dal";
import { compactCount, getDashboardSummary, pesoWhole } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Your reviews — bluntly" };

/**
 * Reviews, built to frame 6159:1510.
 *
 * DOCUMENTED: that frame specifies chrome and nothing else. Its only children
 * are the hero rectangle, the white sheet and the nav bar — no list, no cards,
 * no empty state. So the chrome here is the frame's, exactly; the content is
 * built from the reviewer's own existing data in Bluntly's design system,
 * because there is no composition in Figma to reproduce.
 *
 * This is stated rather than quietly invented: if a composition is added to the
 * frame later, this screen should be rebuilt to it.
 */
export default async function DashboardReviewsPage() {
  const me = await requireOnboardedUser();
  const summary = await getDashboardSummary("90d");
  const reviews = summary?.reviews ?? [];

  return (
    <DashboardScreen
      heroHeight={118}
      /* The frame's hero IS the nav row: its sheet begins 86px below it, with
         nothing in between. The count used to sit here in a 150px orange band
         the design does not have, which pushed the sheet to 235. It now opens
         the sheet instead, so the chrome matches the frame and the reviewer
         still sees their real figures. */
      hero={null}
    >
      <div className="pb-12">
        <div className="px-4 pb-2">
          <p className="text-[13px] text-[var(--text-secondary)]">Your reviews</p>
          <p className="mt-0.5 text-[28px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
            {reviews.length}
          </p>
          <p className="mt-1 text-[12px] text-[var(--text-muted)]">
            ranked by what they have earned
          </p>
        </div>
        {reviews.length === 0 ? (
          <div className="px-4 py-10 text-center">
            <p className="text-[14px] text-[var(--text-primary)]">
              You have not published a review yet.
            </p>
            <Link
              href="/reviews/new"
              className="mt-4 inline-flex items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 py-2.5 text-[13px] font-semibold text-[var(--text-on-brand)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
            >
              Write your first review
            </Link>
          </div>
        ) : (
          <ol>
            {reviews.map((review) => (
              <li key={review.review_id} className="border-b border-[var(--border-subtle)] last:border-0">
                <Link
                  href={`/reviews/${review.review_id}`}
                  className="flex items-center gap-3 px-4 py-4 transition-colors hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
                >
                  <span className="relative block h-16 w-16 shrink-0 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--line-hairline-10)]">
                    {review.photo_url ? (
                      <Image src={review.photo_url} alt="" fill sizes="128px" className="object-cover" />
                    ) : (
                      <span aria-hidden="true" className="absolute inset-0 grid place-items-center">
                        <ImageSquare size={20} weight="light" className="text-[var(--text-muted)]" />
                      </span>
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-[var(--text-primary)]">
                      {review.title}
                    </span>
                    <span className="mt-1 block text-[12px] text-[var(--text-secondary)]">
                      {compactCount(review.views)} views
                      <span className="mx-1.5 opacity-50">·</span>
                      {compactCount(review.helped)} helped
                    </span>
                    <span className="mt-1 block text-[14px] font-bold text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
                      {pesoWhole(review.earnings)}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}

        <p className="mt-6 px-4 text-[12px] text-[var(--text-muted)]">
          Showing {me.username ? `@${me.username}` : "your"} published reviews.{" "}
          <Link href="/profile" className="underline hover:text-[var(--accent-primary)]">
            Your public profile
          </Link>
        </p>
      </div>
    </DashboardScreen>
  );
}
