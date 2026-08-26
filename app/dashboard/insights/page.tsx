import type { Metadata } from "next";
import Link from "next/link";

import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { AreaChart, type Point } from "@/components/dashboard/MiniChart";
import { requireOnboardedUser } from "@/lib/dal";
import { compactCount, getDashboardSummary, peso } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Insights — bluntly" };

/**
 * Insights, built to frame 5762:752.
 *
 * The frame's elements were split before any of it was written, because one of
 * them cannot be built truthfully yet:
 *
 *   EXISTING DATA          the dated area chart, reviews published, people
 *                          helped, total views, earnings
 *   REQUIRES NEW TELEMETRY the "Streak" card — a flame, "6 days", and a
 *                          month grid of filled dots
 *
 * The streak is not built, and deliberately not faked. "Streak" on a
 * contributor's own analytics screen can honestly mean either days they
 * CONTRIBUTED (derivable today from reviews, questions and answers) or days
 * they READ the site (which needs reader-session tracking that does not exist
 * and would need a privacy ruling). Those are different products, and choosing
 * the convenient one would be silently redefining a designed feature to make it
 * implementable. It is raised as an owner question instead.
 *
 * The rest of the frame is real, so the route ships rather than being held
 * hostage to one widget.
 */
export default async function InsightsPage() {
  await requireOnboardedUser();
  const summary = await getDashboardSummary("30d");

  // Total daily views across the reviewer's own reviews. Each row carries a
  // dense per-day series over the same window, so summing them is exact and
  // needs no second endpoint.
  const days = summary?.reviews?.[0]?.series?.length ?? 0;
  const viewSeries: Point[] = Array.from({ length: days }, (_, i) => ({
    day: summary!.reviews[0].series[i].day,
    amount: (summary?.reviews ?? []).reduce(
      (total, review) => total + Number(review.series[i]?.amount ?? 0),
      0,
    ),
  }));
  const totalViews = summary?.total_views ?? 0;
  const helped = (summary?.reviews ?? []).reduce((a, r) => a + r.helped, 0);

  return (
    <DashboardScreen
      heroHeight={300}
      hero={
        <div className="px-6 pb-14 pt-8 text-center">
          <p className="text-[13px] font-medium text-white/80">Insights</p>
          <p className="mt-1 text-[13px] text-white/85">
            How your reviews are doing over the last 30 days
          </p>
        </div>
      }
    >
      <div className="px-4 pb-12">
        <section
          aria-labelledby="reach-heading"
          className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-5 py-4 shadow-[var(--shadow-card)]"
        >
          <div className="flex items-center justify-between">
            <h2 id="reach-heading" className="text-[13px] font-semibold text-[var(--text-primary)]">
              Reach
            </h2>
            <span className="text-[12px] text-[var(--text-secondary)]">This month</span>
          </div>

          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
            <Stat value={compactCount(totalViews)} label="Views" />
            <Stat value={compactCount(helped)} label="People helped" />
            <Stat value={String(summary?.reviews?.length ?? 0)} label="Reviews" />
            <Stat
              value={summary ? peso(summary.estimated_commission) : peso(0)}
              label="Earned"
            />
          </dl>

          <div className="mt-5 h-[120px]">
            {viewSeries.length > 0 && totalViews > 0 ? (
              /* Labelled explicitly as views. The frame's series is unlabelled,
                 and an unlabelled money-or-traffic curve on an earnings product
                 is the kind of ambiguity that gets misread. */
              <AreaChart
                points={viewSeries}
                label={`Daily views across your reviews over the last 30 days, ${totalViews} in total.`}
              />
            ) : (
              <div className="flex h-full items-center justify-center rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
                <p className="text-[12px] text-[var(--text-muted)]">
                  No views recorded for this period yet.
                </p>
              </div>
            )}
          </div>
          <p className="mt-2 text-[11px] text-[var(--text-muted)]">
            Daily views &mdash; times your reviews were opened, not unique readers.
          </p>
        </section>

        {/* The one element that is not built. Shown rather than hidden: the
            frame has it, and a reviewer should see that it is coming and why it
            is not here, instead of finding a silently missing card. */}
        <section
          aria-labelledby="streak-heading"
          className="mt-5 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-5 py-4 shadow-[var(--shadow-card)]"
        >
          <h2 id="streak-heading" className="text-[13px] font-semibold text-[var(--text-primary)]">
            Streak
          </h2>
          <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
            Not available yet. Showing a streak means deciding what it counts
            &mdash; days you published something, or days you visited &mdash; and
            those are different measurements. It will appear here once that is
            settled, rather than showing a number that might mean the wrong thing.
          </p>
        </section>

        <p className="mt-8 text-[12px] text-[var(--text-muted)]">
          <Link href="/dashboard/history" className="underline hover:text-[var(--accent-primary)]">
            See how each review earned
          </Link>
        </p>
      </div>
    </DashboardScreen>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dd className="text-[19px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {value}
      </dd>
      <dt className="mt-1 text-[11px] text-[var(--text-secondary)]">{label}</dt>
    </div>
  );
}
