import type { Metadata } from "next";
import Link from "next/link";

import { AreaChart, type Point } from "@/components/dashboard/MiniChart";
import { StreakCard } from "@/components/dashboard/StreakCard";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireOnboardedUser } from "@/lib/dal";
import { compactCount, getDashboardSummary, getStreak } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Insights — bluntly" };

/**
 * Insights, built to frame 5762:752.
 *
 * This frame does NOT share the chrome of the other dashboard screens. It uses
 * the ordinary site header — wordmark, search, avatar — over a shallow gradient
 * band, not the back-arrow-and-Contributor-pill nav. It was first built on the
 * shared chrome, which was wrong, and the frame's own composition is a Streak
 * block and a dated chart sitting directly on the white sheet: no cards around
 * them, and no stats strip.
 *
 * The Streak block was open on an ambiguity — days CONTRIBUTED or days READ —
 * and the owner settled it on 2026-08-27 as a CONTRIBUTION streak. It is built
 * from timestamps the application already persists (published reviews,
 * questions, answers, price observations), so no reading or browsing telemetry
 * was added, and none is implied. The frame's "6 days" is a sample: the number
 * rendered is whatever the reviewer has actually earned, including zero.
 *
 * Avg. read time remains absent and remains an OWNER/PRIVACY DECISION. It is
 * not the same thing as an estimated reading time computed from word count,
 * and one must never be shown in the other's place.
 */
export default async function InsightsPage() {
  const me = await requireOnboardedUser();
  // Independent of each other, so they are not serialised.
  const [summary, streak] = await Promise.all([
    getDashboardSummary("30d"),
    getStreak(),
  ]);

  // Total daily views across the reviewer's own reviews. Every row carries a
  // dense per-day series over the same window, so summing them is exact.
  const days = summary?.reviews?.[0]?.series?.length ?? 0;
  const viewSeries: Point[] = Array.from({ length: days }, (_, i) => ({
    day: summary!.reviews[0].series[i].day,
    amount: (summary?.reviews ?? []).reduce(
      (total, review) => total + Number(review.series[i]?.amount ?? 0),
      0,
    ),
  }));
  const totalViews = summary?.total_views ?? 0;
  const hasChart = viewSeries.length > 0 && totalViews > 0;

  // Axis labels come from the data, never from the frame's sample numbers.
  const peak = hasChart ? Math.max(...viewSeries.map((p) => p.amount)) : 0;
  const yTicks = hasChart ? [peak, Math.round(peak / 2), 0] : [];
  const xTicks = hasChart
    ? [0, Math.floor((viewSeries.length - 1) / 2), viewSeries.length - 1]
        .filter((v, i, a) => a.indexOf(v) === i)
        .map((i) => {
          const d = new Date(`${viewSeries[i].day}T00:00:00`);
          return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
        })
    : [];

  return (
    <>
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />

      <div className="mx-auto w-full max-w-[430px] lg:max-w-[46rem]">
        {/* The frame's shallow gradient band between the header and the sheet. */}
        <div
          className="h-[212px]"
          style={{
            background:
              "linear-gradient(160deg, var(--accent-primary) 0%, var(--accent-strong, #c2410c) 100%)",
          }}
        />

        <div className="relative -mt-8 min-h-[40vh] rounded-t-[28px] bg-[var(--surface-app)] px-5 pb-12 pt-8">
          <StreakCard streak={streak} />

          <section aria-labelledby="views-heading" className="mt-10">
            <h2 id="views-heading" className="sr-only">
              Daily views
            </h2>

            {hasChart ? (
              <>
                <div className="flex items-stretch gap-2">
                  <div className="min-w-0 flex-1">
                    <AreaChart
                      points={viewSeries}
                      label={`Daily views across your reviews over the last 30 days, ${totalViews} in total.`}
                    />
                  </div>
                  {/* The frame carries its value axis on the right. */}
                  <ul
                    aria-hidden
                    className="flex w-9 shrink-0 flex-col justify-between py-0.5 text-[10px] text-[var(--text-muted)] [font-variant-numeric:tabular-nums]"
                  >
                    {yTicks.map((t, i) => (
                      <li key={i}>{compactCount(t)}</li>
                    ))}
                  </ul>
                </div>

                <div
                  aria-hidden
                  className="mt-1.5 flex justify-between pr-11 text-[10px] text-[var(--text-muted)] [font-variant-numeric:tabular-nums]"
                >
                  {xTicks.map((t) => (
                    <span key={t}>{t}</span>
                  ))}
                </div>

                {/* The frame's series is unlabelled. On a product that pays
                    people, an unlabelled curve reads as money. */}
                <p className="mt-3 text-[11px] text-[var(--text-muted)]">
                  Daily views &mdash; times your reviews were opened, not unique
                  readers. {compactCount(totalViews)} in the last 30 days.
                </p>
              </>
            ) : (
              <div className="flex h-[120px] items-center justify-center rounded-[var(--radius-sm)] bg-[var(--surface-card)]">
                <p className="text-[12px] text-[var(--text-muted)]">
                  No views recorded for this period yet.
                </p>
              </div>
            )}
          </section>

          <p className="mt-10 text-[12px] text-[var(--text-muted)]">
            <Link
              href="/dashboard/history"
              className="underline hover:text-[var(--accent-primary)]"
            >
              See how each review earned
            </Link>
          </p>
        </div>
      </div>
    </>
  );
}
