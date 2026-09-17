import type { Metadata } from "next";
import Link from "next/link";
import { CaretRight, ChartLineUp } from "@phosphor-icons/react/dist/ssr";

import { DashboardScreen, HeroAmount } from "@/components/dashboard/DashboardScreen";
import { AreaChart, type Point } from "@/components/dashboard/MiniChart";
import { StreakCard } from "@/components/dashboard/StreakCard";
import { requireOnboardedUser } from "@/lib/dal";
import { compactCount, DASHBOARD_RANGES, getDashboardSummary, getStreak } from "@/lib/dashboard";
import { trustLevel } from "@/lib/trust";

export const metadata: Metadata = { title: "Insights — bluntly" };

/**
 * Insights.
 *
 * NO FIGMA SOURCE. Its frame, 5762:752, is no longer in the file (checked
 * 2026-09-17), and the owner's direction that day was to design it so it sits
 * with the rest of the dashboard. So it is composed only from what the four
 * dashboard frames already establish, and invents no visual language:
 *
 *   chrome     DashboardScreen — the gradient, the back arrow and trust pill,
 *              the white sheet with its 32px top — as Transfer, History and
 *              Reviews use it (5762:332, 5762:472, 6159:1510)
 *   headline   HeroAmount, the entry dashboard's centred figure (6164:1694)
 *   range      the leaderboard's segmented toggle (5991:443)
 *   cards      the Est. Comm card: white, radius 12, 0 4 2 25% drop shadow,
 *              a 16px glyph before a 12px Medium title, 14px values over 10px
 *              Light labels (5961:773, 5702:2804)
 *
 * It used to sit under the ordinary site header on an orange-to-#c2410c band
 * and a grey sheet — the chrome of the deleted frame, and a ramp the other
 * dashboard screens had already dropped.
 *
 * WHAT THE FIGURES ARE. `/users/me/dashboard` returns daily views only per
 * ranked review, for at most five reviews (TOP_REVIEWS). The chart, and every
 * figure beside it, is the sum of those series, so the card never states a
 * total its own chart does not show; when the list is at its cap the card says
 * the figures cover the top five. The hero is the account-wide view total the
 * same response carries. The streak is the owner's CONTRIBUTION streak
 * (2026-08-27). Avg. read time is still not measured and is not shown.
 */
export default async function InsightsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  const me = await requireOnboardedUser();
  const requested = (await searchParams).range;
  const range = DASHBOARD_RANGES.find((r) => r.key === requested) ?? DASHBOARD_RANGES[1];
  // Independent of each other, so they are not serialised.
  const [summary, streak] = await Promise.all([getDashboardSummary(range.key), getStreak()]);

  const reviews = summary?.reviews ?? [];
  const capped = reviews.length >= 5;
  const days = reviews[0]?.series?.length ?? 0;
  const viewSeries: Point[] = Array.from({ length: days }, (_, i) => ({
    day: reviews[0].series[i].day,
    amount: reviews.reduce((total, review) => total + Number(review.series[i]?.amount ?? 0), 0),
  }));
  const seriesTotal = viewSeries.reduce((total, p) => total + p.amount, 0);
  const hasChart = seriesTotal > 0;
  const best = hasChart
    ? viewSeries.reduce((top, p) => (p.amount > top.amount ? p : top), viewSeries[0])
    : null;
  const shortDate = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString("en-PH", { month: "short", day: "numeric" });
  const xTicks = hasChart
    ? [0, Math.floor((viewSeries.length - 1) / 2), viewSeries.length - 1]
        .filter((v, i, a) => a.indexOf(v) === i)
        .map((i) => shortDate(viewSeries[i].day))
    : [];

  return (
    <DashboardScreen
      user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }}
      title="Insights"
      backHref="/dashboard"
      // The 72px bar and HeroAmount's 152px, with the sheet's 32px overlap below.
      heroHeight={256}
      trustLevel={trustLevel(me.trust_level_name, me.trust_stage)}
      hero={
        <HeroAmount
          label={`Total Views · ${range.label}`}
          amount={summary ? summary.total_views.toLocaleString("en-PH") : "—"}
        />
      }
    >
      <div className="flex flex-col gap-5 pb-12 lg:gap-6">
        {/* The leaderboard toggle (5991:443), here choosing the window. Links,
            so the choice is in the address and survives back and reload. */}
        <nav
          aria-label="Period"
          className="mx-4 flex h-10 w-fit items-center gap-1 rounded-[24px] bg-[#f2f2f2] p-1 shadow-[inset_0_2px_4px_rgba(0,0,0,0.25)] lg:mx-0"
        >
          {DASHBOARD_RANGES.map((r) => {
            const current = r.key === range.key;
            return (
              <Link
                key={r.key}
                href={`/dashboard/insights?range=${r.key}`}
                scroll={false}
                aria-current={current ? "page" : undefined}
                className={`inline-flex h-8 items-center rounded-[16px] px-4 text-[12px] font-medium leading-none text-[var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                  current
                    ? "bg-[var(--surface-card)] [filter:drop-shadow(0_2px_2px_rgba(0,0,0,0.25))]"
                    : "transition-colors hover:text-[var(--accent-primary)]"
                }`}
              >
                {r.label}
              </Link>
            );
          })}
        </nav>

        <section
          aria-labelledby="views-heading"
          className="mx-4 rounded-[12px] bg-[var(--surface-card)] px-6 pb-6 pt-4 [filter:drop-shadow(0_4px_2px_rgba(0,0,0,0.25))] lg:mx-0"
        >
          <h2
            id="views-heading"
            className="flex items-center gap-1 text-[12px] font-medium leading-none text-[var(--text-primary)]"
          >
            <ChartLineUp size={16} weight="regular" />
            Daily views
          </h2>

          {hasChart && best ? (
            <>
              <dl className="mt-5 flex gap-6">
                <Figure value={compactCount(seriesTotal)} label="Views" />
                <Figure value={compactCount(Math.round(seriesTotal / viewSeries.length))} label="Daily average" />
                <Figure value={compactCount(best.amount)} label={`Best day · ${shortDate(best.day)}`} />
              </dl>

              <div className="mt-5 h-[111px]">
                <AreaChart
                  points={viewSeries}
                  label={`Daily views, ${range.label.toLowerCase()}: ${seriesTotal} in total, most on ${shortDate(best.day)}.`}
                />
              </div>
              <div
                aria-hidden
                className="mt-1.5 flex justify-between text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)] [font-variant-numeric:tabular-nums]"
              >
                {xTicks.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
            </>
          ) : (
            <div className="mt-5 flex h-[111px] items-center justify-center rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
              <p className="px-4 text-center text-[12px] text-[var(--text-secondary)]">
                No views recorded {range.label.toLowerCase()} yet.
              </p>
            </div>
          )}

          {/* An unlabelled curve on a product that pays people reads as money. */}
          <p className="mt-4 text-[10px] font-light leading-[15px] text-[rgba(32,32,32,0.7)]">
            Times your reviews were opened, not unique readers
            {capped ? ", across your five top-earning reviews" : ""}.
          </p>
        </section>

        <StreakCard streak={streak} />

        <Link
          href="/dashboard/history"
          className="mx-4 inline-flex w-fit items-center gap-1 text-[10px] leading-none text-[rgba(32,32,32,0.7)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] lg:mx-0"
        >
          See how each review earned
          <CaretRight size={8} weight="bold" />
        </Link>
      </div>
    </DashboardScreen>
  );
}

/** A value over its label, as the Est. Comm card sets them (5702:2804). */
function Figure({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex min-w-0 flex-col-reverse">
      <dt className="mt-1 whitespace-nowrap text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)]">
        {label}
      </dt>
      <dd className="text-[14px] leading-none text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
        {value}
      </dd>
    </div>
  );
}
