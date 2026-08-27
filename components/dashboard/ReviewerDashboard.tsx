import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  Books,
  CaretRight,
  ChartLineUp,
  ClockCounterClockwise,
  CoinVertical,
  DotOutline,
  ImageSquare,
  PaperPlaneTilt,
  PenNib,
  UserSound,
} from "@phosphor-icons/react/dist/ssr";

import { AreaChart, Sparkline, type Point } from "@/components/dashboard/MiniChart";
import {
  compactCount,
  DASHBOARD_RANGES,
  peso,
  pesoWhole,
  type DashboardReviewRow,
  type DashboardSummary,
} from "@/lib/dashboard";

/**
 * The reviewer dashboard, built to the approved Figma frame (5572:7130).
 *
 * The design is a 390px phone frame, so the geometry below is its geometry:
 * a 72px nav, the earnings figure centred at y=168, a 300x72 action bar
 * floating over the curve at y=321, a 358px card, and 120px list rows with
 * 80x80 thumbnails under 32px medals. Wider screens keep that composition and
 * centre it rather than inventing a desktop layout the design does not
 * specify.
 *
 * Every number here comes from `/users/me/dashboard`. Where the design shows a
 * figure nothing measures — average read time — the tile says so instead of
 * displaying a plausible substitute, because a reviewer makes decisions about
 * their own work on this screen.
 */

const toPoints = (series: { day: string; amount: string }[]): Point[] =>
  series.map((p) => ({ day: p.day, amount: Number(p.amount) }));

export function ReviewerDashboard({
  summary,
  range,
  displayName,
}: {
  summary: DashboardSummary | null;
  range: string;
  displayName: string;
}) {
  const rangeLabel =
    DASHBOARD_RANGES.find((r) => r.key === range)?.label ?? "This week";

  return (
    <div className="mx-auto w-full max-w-[430px] lg:max-w-[46rem]">
      <EarningsHero
        amount={summary ? peso(summary.estimated_commission) : peso(0)}
      />
      <ActionBar />
      <EstCommCard summary={summary} rangeLabel={rangeLabel} range={range} />
      <Leaderboard summary={summary} displayName={displayName} />
    </div>
  );
}

/** Orange gradient, back arrow, Contributor pill, and the headline figure. */
function EarningsHero({ amount }: { amount: string }) {
  return (
    // The gradient is the hero's OWN background, not an absolutely positioned
    // overlay. As an overlay it painted above the later, non-positioned card
    // and hid its header row — positioned elements win against non-positioned
    // siblings regardless of document order.
    <div
      className="rounded-b-[28px]"
      style={{
        background:
          "linear-gradient(160deg, var(--accent-primary) 0%, var(--accent-strong, #c2410c) 100%)",
      }}
    >
      <div>
        <div className="flex h-[72px] items-center justify-between px-6">
          <Link
            href="/"
            aria-label="Back"
            className="-ml-1 rounded-full p-1 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
          >
            <ArrowLeft size={28} weight="regular" />
          </Link>

          {/* The design's white pill with the mark and the role. */}
          <span className="inline-flex h-8 items-center gap-2 rounded-[var(--radius-pill)] bg-white pl-3 pr-4">
            <Image
              src="/icon.svg"
              alt=""
              width={16}
              height={16}
              className="h-4 w-4"
            />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              Contributor
            </span>
          </span>
        </div>

        <div className="pb-[96px] pt-[48px] text-center">
          <p className="text-[13px] font-medium text-white/80">Est. Comm</p>
          <p className="mt-1 text-[40px] font-bold leading-tight text-white [font-variant-numeric:tabular-nums]">
            {amount}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * The four screens the approved flow leads to.
 *
 * These were same-page anchors while the screens did not exist. They are their
 * own frames — Transfer 5762:332, History 5762:472, Reviews 6159:1510,
 * Insights 5762:752 — and are now their own routes, so browser back/forward and
 * direct navigation behave as the flow intends.
 */
const ACTIONS = [
  { href: "/dashboard/transfer", label: "Transfer", Icon: PaperPlaneTilt },
  { href: "/dashboard/history", label: "History", Icon: ClockCounterClockwise },
  { href: "/dashboard/reviews", label: "Reviews", Icon: Books },
  { href: "/dashboard/insights", label: "Insights", Icon: ChartLineUp },
];

/** The floating white bar that straddles the curve. */
function ActionBar() {
  return (
    <div className="relative z-10 -mt-[72px] px-[45px]">
      <nav
        aria-label="Earnings actions"
        className="flex h-[72px] items-center justify-between rounded-[var(--radius-md)] bg-[var(--surface-card)] px-7 shadow-[var(--shadow-card)]"
      >
        {ACTIONS.map(({ href, label, Icon }) => (
          <Link
            key={label}
            href={href}
            className="flex w-[46px] flex-col items-center gap-1.5 rounded-[var(--radius-sm)] py-1 text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <Icon size={26} weight="regular" />
            <span className="text-[11px] font-medium leading-none">{label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}

function EstCommCard({
  summary,
  rangeLabel,
  range,
}: {
  summary: DashboardSummary | null;
  rangeLabel: string;
  range: string;
}) {
  const next =
    DASHBOARD_RANGES[
      (DASHBOARD_RANGES.findIndex((r) => r.key === range) + 1) %
        DASHBOARD_RANGES.length
    ];

  return (
    <section
      id="insights"
      aria-labelledby="est-comm-heading"
      className="mx-4 mt-5 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-6 py-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex items-center justify-between">
        <h2
          id="est-comm-heading"
          className="flex items-center gap-2 text-[13px] font-semibold text-[var(--text-primary)]"
        >
          <CoinVertical size={16} weight="regular" />
          Est. Comm
          <CaretRight size={8} weight="bold" className="text-[var(--text-muted)]" />
        </h2>

        {/* A real control, not the decorative caret the frame shows: it cycles
            the window the whole card is drawn from. */}
        <Link
          href={`/dashboard?range=${next.key}`}
          scroll={false}
          className="flex items-center gap-1 text-[12px] font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
        >
          {rangeLabel}
          <CaretRight size={8} weight="bold" />
        </Link>
      </div>

      <dl className="mt-5 flex gap-6">
        <Stat
          value={summary ? `+${pesoWhole(summary.earned_in_window)}` : "—"}
          label="Earned"
          tone="success"
        />
        <Stat
          value={summary ? compactCount(summary.total_views) : "—"}
          label="Total Views"
          tone="success"
        />
        {/* Nothing measures read time. The design shows "4m 3s"; inventing one
            here would be a number a reviewer might act on. */}
        <Stat
          value="—"
          label="Avg. Read time"
          tone="muted"
          note="Not measured yet"
        />
      </dl>

      <div className="mt-6 h-[111px]">
        {/* A dense series of zeros is not data. Drawing it produced a bare
            line pinned to the axis under an empty card, which reads as a
            broken chart rather than as an empty month. */}
        {summary && summary.series.length > 0 && summary.has_earnings ? (
          <AreaChart
            points={toPoints(summary.series)}
            label={`Daily earnings, ${rangeLabel.toLowerCase()}. ${
              summary.has_earnings
                ? `Total ${peso(summary.earned_in_window)}.`
                : "No earnings in this period."
            }`}
          />
        ) : (
          <div className="flex h-full items-center justify-center rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
            <p className="text-[12px] text-[var(--text-muted)]">
              No earnings data for this period yet.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({
  value,
  label,
  tone,
  note,
}: {
  value: string;
  label: string;
  tone: "success" | "muted";
  note?: string;
}) {
  return (
    <div className="min-w-0">
      <dd
        className={`text-[17px] font-semibold leading-tight [font-variant-numeric:tabular-nums] ${
          tone === "success"
            ? "text-[var(--accent-success)]"
            : "text-[var(--text-muted)]"
        }`}
      >
        {value}
      </dd>
      <dt className="mt-1 whitespace-nowrap text-[11px] text-[var(--text-secondary)]">
        {label}
      </dt>
      {note ? (
        <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{note}</p>
      ) : null}
    </div>
  );
}

/** Medal colours for the top three, as the design draws them. */
const MEDAL = [
  "bg-[#F5B301] text-white",
  "bg-[#B6BCC4] text-white",
  "bg-[#C67A3E] text-white",
];

function Leaderboard({
  summary,
  displayName,
}: {
  summary: DashboardSummary | null;
  displayName: string;
}) {
  const reviews = summary?.reviews ?? [];

  return (
    <section aria-labelledby="leaderboard-heading" className="mt-6">
      <h2 id="leaderboard-heading" className="sr-only">
        {displayName}&rsquo;s reviews, ranked
      </h2>

      <div className="border-t border-[var(--border-subtle)] pt-4">
        {/* Reviews / Answers. Answers is not a dashboard surface yet, so it is
            a link to the Q&A the reviewer has answered rather than a tab that
            switches to an empty panel. */}
        <div className="mx-4 flex w-fit items-center gap-1 rounded-[var(--radius-pill)] bg-[var(--surface-app)] p-1">
          <span className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-4 py-1.5 text-[13px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-card)]">
            <PenNib size={16} weight="regular" />
            Reviews
          </span>
          <Link
            href="/questions"
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] px-4 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <UserSound size={16} weight="regular" />
            Answers
          </Link>
        </div>

        {reviews.length === 0 ? (
          <p className="mx-4 mt-6 text-[13px] text-[var(--text-secondary)]">
            Your published reviews will be ranked here once they start earning.
          </p>
        ) : (
          <ol className="mt-4">
            {reviews.map((review, i) => (
              <LeaderboardRow key={review.review_id} review={review} rank={i + 1} />
            ))}
          </ol>
        )}

        {reviews.length > 0 ? (
          <Link
            href="/profile"
            className="mx-4 mt-4 inline-block text-[12px] text-[var(--text-secondary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            See more...
          </Link>
        ) : null}
      </div>
    </section>
  );
}

function LeaderboardRow({
  review,
  rank,
}: {
  review: DashboardReviewRow;
  rank: number;
}) {
  return (
    <li className="border-b border-[var(--border-subtle)] last:border-0">
      <Link
        href={`/reviews/${review.review_id}`}
        className="flex items-center gap-3 px-4 py-5 transition-colors hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
      >
        <span className="relative block h-20 w-20 shrink-0">
          <span className="relative block h-20 w-20 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
            {review.photo_url ? (
              <Image
                src={review.photo_url}
                alt=""
                fill
                sizes="160px"
                className="object-cover"
              />
            ) : (
              <span
                aria-hidden="true"
                className="absolute inset-0 grid place-items-center bg-[var(--line-hairline-10)]"
              >
                <ImageSquare size={22} weight="light" className="text-[var(--text-muted)]" />
              </span>
            )}
          </span>
          {/* The medal sits over the thumbnail's top-right, as in the frame.
              The rank is text inside it, so it is not colour-only. */}
          <span
            aria-hidden="true"
            className={`absolute -right-2 -top-1 grid h-8 w-8 place-items-center rounded-full text-[13px] font-bold shadow-[var(--shadow-card)] ${
              MEDAL[rank - 1] ?? "bg-[var(--surface-inverse)] text-white"
            }`}
          >
            {rank}
          </span>
        </span>

        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium text-[var(--text-primary)]">
            {review.title}
          </span>
          <span className="mt-1 flex items-center text-[12px] text-[var(--text-secondary)]">
            {compactCount(review.views)} views
            <DotOutline size={12} weight="fill" className="mx-0.5" />
            {compactCount(review.helped)} helped
          </span>
          <span className="mt-1 block text-[15px] font-bold text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
            {pesoWhole(review.earnings)}
          </span>
        </span>

        {/* 100x70, the frame's own size — it fits at 390 alongside an 80px
            thumbnail and the title column. */}
        <span className="block h-[70px] w-[100px] shrink-0">
          <Sparkline
            points={toPoints(review.series)}
            label={`Daily views for ${review.title}`}
          />
        </span>
      </Link>
    </li>
  );
}
