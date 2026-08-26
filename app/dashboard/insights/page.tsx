import type { Metadata } from "next";
import Link from "next/link";
import { CaretRight } from "@phosphor-icons/react/dist/ssr";

import { AreaChart, type Point } from "@/components/dashboard/MiniChart";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireOnboardedUser } from "@/lib/dal";
import { compactCount, getDashboardSummary } from "@/lib/dashboard";

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
 * The frame's elements were split by what can be built truthfully:
 *
 *   EXISTING DATA          the dated area chart — real daily views
 *   REQUIRES NEW TELEMETRY the Streak block: a flame, "6 days", and a month
 *                          grid of filled dots
 *
 * The streak is not built, and deliberately not faked. "Streak" here can
 * honestly mean days the reviewer CONTRIBUTED (derivable today from reviews,
 * questions and answers) or days they READ the site (which needs reader-session
 * tracking that does not exist and would need a privacy ruling). Those are
 * different products, and picking the convenient one would be silently
 * redefining a designed feature to make it implementable. It is an owner
 * question instead, and the block says so where the number would go.
 */
export default async function InsightsPage() {
  const me = await requireOnboardedUser();
  const summary = await getDashboardSummary("30d");

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
          <section aria-labelledby="streak-heading">
            <div className="flex items-baseline justify-between">
              <h2
                id="streak-heading"
                className="text-[13px] font-semibold text-[var(--text-primary)]"
              >
                Streak
              </h2>
              <span className="flex items-center gap-0.5 text-[12px] text-[var(--text-secondary)]">
                This month
                <CaretRight size={11} weight="bold" />
              </span>
            </div>

            {/* Where the flame and "6 days" sit in the frame. Left empty of a
                number rather than filled with a plausible one. */}
            <p className="mt-3 max-w-[34rem] text-[13px] leading-relaxed text-[var(--text-secondary)]">
              Not available yet. Showing a streak means deciding what it counts
              &mdash; days you published something, or days you visited &mdash;
              and those are different measurements. It will appear here once
              that is settled, rather than showing a number that might mean the
              wrong thing.
            </p>
          </section>

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
