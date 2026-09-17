import type { Metadata } from "next";
import Link from "next/link";

import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { RankedReviewRow } from "@/components/dashboard/ReviewerDashboard";
import { requireOnboardedUser } from "@/lib/dal";
import { trustLevel } from "@/lib/trust";
import { getDashboardSummary } from "@/lib/dashboard";

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
      user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }}
      title="Your reviews"
      heroHeight={104}
      trustLevel={trustLevel(me.trust_level_name, me.trust_stage)}
      /* The frame's hero IS the nav row: the sheet's top edge is the nav's foot
         (y120 in the frame, 72 under its status bar — measured on the export
         2026-09-17; it had been set 14px lower), with nothing in between. The count used to sit here in a 150px orange band
         the design does not have, which pushed the sheet to 235. It now opens
         the sheet instead, so the chrome matches the frame and the reviewer
         still sees their real figures. */
      hero={null}
    >
      <div className="pb-12">
        {/* No frame draws this content (see above), so it is set in the
            dashboard's own type — the label in 12px Medium, the caption in 10px
            Light at 70% — and the rows are the leaderboard's rows (5991:608).

            WHAT THE LIST IS. `/users/me/dashboard` returns the top five reviews
            (TOP_REVIEWS in dashboard_service.py), ranked by lifetime earnings,
            with views counted inside the requested window. The screen used to
            title that "Your reviews" over a count, which reads as every review
            the account has; for anyone with more than five it was wrong. */}
        <section aria-labelledby="reviews-heading" className="px-4 pb-2">
          <h2 id="reviews-heading" className="text-[12px] font-medium leading-none text-[var(--text-primary)]">
            Your top reviews
          </h2>
          <p className="mt-1.5 text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)]">
            Ranked by lifetime earnings · views from the last 90 days
          </p>
        </section>
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
          <ol className="mt-2">
            {reviews.map((review, i) => (
              <RankedReviewRow key={review.review_id} review={review} rank={i + 1} />
            ))}
          </ol>
        )}

        <p className="mt-6 px-4 text-[12px] text-[var(--text-secondary)]">
          Every review you have published is on{" "}
          <Link href="/profile" className="underline underline-offset-2 hover:text-[var(--accent-primary)]">
            your profile
          </Link>
          .
        </p>
      </div>
    </DashboardScreen>
  );
}
