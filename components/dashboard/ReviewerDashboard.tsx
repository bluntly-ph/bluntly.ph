import Image from "next/image";
import Link from "next/link";
import {
  Books,
  CaretRight,
  ChartLineUp,
  ClockCounterClockwise,
  CoinVertical,
  DotOutline,
  ImageSquare,
  PaperPlaneTilt,
  PenNib,
  Seal,
  UserSound,
} from "@phosphor-icons/react/dist/ssr";

import { DASHBOARD_GRADIENT, DashboardNav, HeroAmount } from "@/components/dashboard/DashboardScreen";
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
 * 80x80 thumbnails under 32px medals.
 *
 * WEBSITE: centring that phone composition on a monitor is what the owner
 * rejected (review, 2026-09-16). From `md` the column widens; from `lg` the
 * earnings hero, its action bar and the Est. Comm card form the left column and
 * the ranked reviews sit beside them as their own card.
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
  trustLevel,
}: {
  summary: DashboardSummary | null;
  range: string;
  displayName: string;
  /** The account's computed level; see DashboardScreen's `trustLevel`. */
  trustLevel: string;
}) {
  const rangeLabel =
    DASHBOARD_RANGES.find((r) => r.key === range)?.label ?? "This week";

  return (
    // White under 768px: in 5572:7130 the sheet below the curve is one white
    // surface down to the last row. Without it the rows sat on the page's grey
    // (compared 2026-09-17), while the wallet section after them stays on grey.
    <div className="mx-auto w-full max-w-[430px] max-md:bg-[var(--surface-card)] md:max-w-[40rem] md:pt-6 lg:grid lg:max-w-[64rem] lg:grid-cols-[26rem_minmax(0,1fr)] lg:items-start lg:gap-10 lg:px-10 lg:pt-10">
      <div>
        <EarningsHero
          amount={summary ? peso(summary.estimated_commission) : peso(0)}
          trustLevel={trustLevel}
        />
        <ActionBar />
        <EstCommCard summary={summary} rangeLabel={rangeLabel} range={range} />
      </div>
      <Leaderboard summary={summary} displayName={displayName} />
    </div>
  );
}

/**
 * Gradient, the Profile nav bar and the headline figure (5572:7130). The
 * gradient runs on behind the action bar, and the white sheet's curved top
 * edge starts at y301 (Rectangle 277: radius 32 across, 46 down). The hero was
 * a box with a 28px rounded foot ending 65px higher, which moved every block
 * below it out of place.
 */
function EarningsHero({ amount, trustLevel }: { amount: string; trustLevel: string }) {
  return (
    <div className="md:overflow-hidden md:rounded-[28px]" style={{ background: DASHBOARD_GRADIENT }}>
      <DashboardNav backHref="/" trustLevel={trustLevel} />
      {/* 72 + 229 = 301: the sheet's edge. */}
      <div className="min-h-[229px] md:min-h-0 md:pb-[72px]">
        <HeroAmount label="Est. Comm" amount={amount} />
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

/**
 * The white sheet's curved edge and the floating bar that straddles it
 * (5961:774): 300x72 at x45, y273 — 28px above the edge — white, radius 12, a
 * 0 4 2 25% drop shadow, 15px over and 12px under 28px sides; four 46px items
 * 20px apart, a glyph over a 10px Regular label at 70% ink (Transfer's glyph
 * 24px with a 6px gap, the rest 28px with 2px). It was 26px glyphs over 11px
 * Medium on a bar that ended the hero instead of crossing the sheet.
 */
function ActionBar() {
  return (
    <div className="relative z-10 rounded-t-[32px_46px] bg-[var(--surface-card)] md:rounded-none md:bg-transparent">
      <div className="-mt-[28px] px-[45px] md:-mt-[72px]">
        <nav
          aria-label="Earnings actions"
          className="flex h-[72px] items-start justify-center gap-5 rounded-[12px] bg-[var(--surface-card)] px-7 pb-3 pt-[15px] [filter:drop-shadow(0_4px_2px_rgba(0,0,0,0.25))]"
        >
          {ACTIONS.map(({ href, label, Icon }, i) => (
            <Link
              key={label}
              href={href}
              className={`flex w-[46px] flex-col items-center rounded-[var(--radius-sm)] text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                i === 0 ? "gap-1.5" : "gap-0.5"
              }`}
            >
              <Icon size={i === 0 ? 24 : 28} weight="regular" />
              <span className="text-[10px] leading-none text-[rgba(32,32,32,0.7)]">{label}</span>
            </Link>
          ))}
        </nav>
      </div>
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
      // 5961:773: x16, 20px under the bar, 358 wide, white, radius 12, 16px
      // over and 24px under 24px sides, a 0 4 2 25% drop shadow.
      className="relative mx-4 mt-5 rounded-[12px] bg-[var(--surface-card)] px-6 pb-6 pt-4 [filter:drop-shadow(0_4px_2px_rgba(0,0,0,0.25))] md:mx-0"
    >
      <div className="flex items-center justify-between">
        <h2
          id="est-comm-heading"
          className="flex items-center gap-1 text-[12px] font-medium leading-none text-[var(--text-primary)]"
        >
          <CoinVertical size={16} weight="regular" />
          Est. Comm
          <CaretRight size={8} weight="bold" />
        </h2>

        {/* A real control, not the decorative caret the frame shows: it cycles
            the window the whole card is drawn from. */}
        <Link
          href={`/dashboard?range=${next.key}`}
          scroll={false}
          className="flex items-center gap-1 text-[10px] font-light leading-none text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
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

      <div className="mt-5 h-[111px]">
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
        // 5702:2804: the value in 14px Regular on a tight line, the label
        // 4px under it in 10px Light at 70% ink (was 17px SemiBold over 11px).
        className={`text-[14px] leading-none [font-variant-numeric:tabular-nums] ${
          tone === "success"
            ? "text-[var(--accent-success)]"
            : "text-[var(--text-muted)]"
        }`}
      >
        {value}
      </dd>
      <dt className="mt-1 whitespace-nowrap text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)]">
        {label}
      </dt>
      {note ? (
        <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{note}</p>
      ) : null}
    </div>
  );
}

/** Medal colours for the top three, as the design draws them. */
/** The seal colours 5991:604 and its siblings draw for the top three (read from the frame). */
const MEDAL = ["text-[#FFC30B]", "text-[#C4C4C4]", "text-[#CE894C]"];

function Leaderboard({
  summary,
  displayName,
}: {
  summary: DashboardSummary | null;
  displayName: string;
}) {
  const reviews = summary?.reviews ?? [];

  return (
    <section
      aria-labelledby="leaderboard-heading"
      className="mt-6 lg:mt-0 lg:rounded-[var(--radius-md)] lg:bg-[var(--surface-card)] lg:py-2 lg:shadow-[var(--shadow-card)]"
    >
      <h2 id="leaderboard-heading" className="sr-only">
        {displayName}&rsquo;s reviews, ranked
      </h2>

      {/* A full-bleed rule 21px under the card, the toggle 20px below it (5991:576, 5991:443). */}
      <div className="border-t border-[var(--line-hairline-10)] pt-5 lg:border-t-0">
        {/* Reviews / Answers. Answers is not a dashboard surface yet, so it is
            a link to the Q&A the reviewer has answered rather than a tab that
            switches to an empty panel. */}
        {/* 5991:443: 214x40, #f2f2f2 with a 0 2 4 25% inset shadow, radius
            24, 8px in on the left; the current segment a white 32px pill
            (radius 16, 16px sides, a 0 2 2 25% drop shadow); 16px glyphs 4px
            before 12px Medium; 12px between segments. It was a flat grey chip
            with 13px labels. */}
        <div className="mx-4 flex h-10 w-[214px] items-center gap-3 rounded-[24px] bg-[#f2f2f2] py-1 pl-2 pr-[22px] shadow-[inset_0_2px_4px_rgba(0,0,0,0.25)]">
          <span className="inline-flex h-8 items-center gap-1 rounded-[16px] bg-[var(--surface-card)] px-4 pb-1.5 pt-2 text-[12px] font-medium leading-none text-[var(--text-primary)] [filter:drop-shadow(0_2px_2px_rgba(0,0,0,0.25))]">
            <PenNib size={16} weight="regular" />
            Reviews
          </span>
          <Link
            href="/questions"
            className="inline-flex items-center gap-1 text-[12px] font-medium leading-none text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
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
              <RankedReviewRow key={review.review_id} review={review} rank={i + 1} />
            ))}
          </ol>
        )}

        {reviews.length > 0 ? (
          <Link
            href="/profile"
            className="mx-4 mt-3 inline-block text-[10px] leading-none text-[rgba(32,32,32,0.7)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            See more...
          </Link>
        ) : null}
      </div>
    </section>
  );
}

/**
 * One ranked review: the dashboard's leaderboard row, and the Reviews screen's
 * rows, so the two lists a reviewer moves between read as the same list.
 */
export function RankedReviewRow({
  review,
  rank,
}: {
  review: DashboardReviewRow;
  rank: number;
}) {
  return (
    <li className="border-b border-[var(--line-hairline-10)] last:border-0">
      <Link
        href={`/reviews/${review.review_id}`}
        // 120px rows (5991:608): an 80px photo at radius 16 with its 32px rank
        // seal over the top-right, the text column 12px beyond it — the title in
        // 10px Light, "views • helped" 10px Light at 70% 21px down, the amount
        // 14px SemiBold green 22px lower — and the 100x70 sparkline at x260.
        // It was 13px Medium, 12px and 15px Bold.
        className="flex items-start gap-3 px-4 py-5 transition-colors hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
      >
        <span className="relative block h-20 w-20 shrink-0">
          <span className="relative block h-20 w-20 overflow-hidden rounded-[16px] bg-[var(--surface-app)]">
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
          {/* 5991:604: a 32px Phosphor Seal (fill) 53px in from the photo's
              left and 5px above it, so it overhangs the top-right corner by
              5px, with the rank in 12px white. The frame sets the digit in
              ExtraBold; Poppins 800 is not loaded (one more font file for one
              glyph), so it is Bold. It was a 32px circle with a card shadow.
              The rank is also the list order, so the seal is decoration. */}
          <span
            aria-hidden="true"
            className={`absolute -right-[5px] -top-[5px] grid h-8 w-8 place-items-center ${
              MEDAL[rank - 1] ?? "text-[var(--surface-inverse)]"
            }`}
          >
            <Seal size={32} weight="fill" className="absolute inset-0" />
            <span className="relative text-[12px] font-bold leading-none text-white">{rank}</span>
          </span>
        </span>

        <span className="min-w-0 flex-1 pt-0">
          <span className="block truncate text-[10px] font-light leading-none text-[var(--text-primary)]">
            {review.title}
          </span>
          <span className="mt-[11px] flex items-center text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)]">
            {compactCount(review.views)} views
            <DotOutline size={12} weight="fill" className="mx-0.5" />
            {compactCount(review.helped)} helped
          </span>
          <span className="mt-3 block text-[14px] font-semibold leading-none text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
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
