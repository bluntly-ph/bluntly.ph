import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { CaretRight, Info } from "@phosphor-icons/react/dist/ssr";

import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { requireOnboardedUser } from "@/lib/dal";
import { trustLevel } from "@/lib/trust";
import {
  EARNING_LABEL,
  EARNING_TABS,
  getEarnings,
  peso,
  pesoWhole,
  sumPeso,
  type EarningRow,
} from "@/lib/dashboard";

export const metadata: Metadata = { title: "Earnings history — bluntly" };

/**
 * History, built to frame 5762:472.
 *
 * The frame is unusually well specified: a floating card with all-time income,
 * filter tabs, and rows that expand to show where the money went — price,
 * commission rate, then the 40/30/30 split as Bluntly / Honesty Fund / Yours.
 * Every one of those is a real column on `commissions`, so the screen is a
 * presentation of the canonical ledger rather than a new one.
 *
 * The tabs are the reviewer-facing reading of the canonical pair. "To earn" is
 * deliberately not "Completed": a completed sale that has not been paid is
 * precisely the distinction a reviewer needs, and the word "Completed" hides it.
 */
export default async function HistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const me = await requireOnboardedUser();
  const status = (await searchParams).status ?? "all";
  const history = await getEarnings(status);

  return (
    <DashboardScreen
      user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }}
      title="Earnings history"
      // The sheet's top at 162 (5762:614 at y210, status bar removed) + its 32px overlap.
      heroHeight={194}
      trustLevel={trustLevel(me.trust_level_name, me.trust_stage)}
      hero={
        // max-md:h-[122px]: the hero's own depth under the bar. The card is taller
        // than what is left of it and must hang over the sheet's edge, not push
        // the sheet down (it did, by 14px).
        <div className="px-4 pt-12 max-md:h-[122px] md:pb-14 md:pt-2">
          {/* The frame's floating card, straddling the sheet's edge (5767:991):
              300x88 at x38, 48px under the bar, white, radius 12, a 0 4 4 10%
              shadow; the total in 20px SemiBold and "Est. All time income" in
              12px Regular 20px in; "Historical Bill" a 32px brand pill with
              12px Medium #f2f2f2. It was a full-width card in 26px Bold. */}
          <div className="flex h-[88px] w-[300px] items-center justify-between gap-3 rounded-[12px] bg-[var(--surface-card)] px-5 shadow-[0_4px_4px_rgba(0,0,0,0.1)] max-md:ml-[22px] md:w-auto">
            <div className="min-w-0">
              <p className="text-[20px] font-semibold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {history ? peso(history.all_time) : peso(0)}
              </p>
              <p className="mt-2.5 text-[12px] leading-none text-[var(--text-primary)]">Est. All time income</p>
            </div>
            {/* It was a span drawn as a button, going nowhere. Its destination
                in the file (6158:1240) is the payout list, which the product
                already has as Payment history on /dashboard. A document
                navigation, not <Link>: /dashboard streams in behind its
                loading.tsx, so a client navigation arrived before #history
                existed and never scrolled to it (checked 2026-09-17). */}
            <a
              href="/dashboard#history"
              className="inline-flex h-8 shrink-0 items-center rounded-[16px] bg-[var(--accent-primary)] px-4 pb-1.5 pt-2 text-[12px] font-medium leading-none text-[#f2f2f2] transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
            >
              Historical Bill
            </a>
          </div>
        </div>
      }
    >
      {/* Tabs are links, not client state: the filter belongs in the URL so a
          reviewer can share or reload a filtered view, and back/forward work. */}
      {/* 6152:1185: 12px Regular 32px apart from x24, the current one brand
          orange, 70px under the sheet's edge, over a full-bleed rule 18px down. */}
      <nav aria-label="Filter earnings" className="mt-[46px] flex gap-8 overflow-x-auto px-6 pb-[18px] md:mt-0">
        {EARNING_TABS.map((tab) => {
          const active = tab.key === status;
          const count = history?.counts?.[tab.key];
          return (
            <Link
              key={tab.key}
              href={tab.key === "all" ? "/dashboard/history" : `/dashboard/history?status=${tab.key}`}
              scroll={false}
              aria-current={active ? "page" : undefined}
              className={`shrink-0 text-[12px] leading-none transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                active ? "text-[var(--accent-primary)]" : "text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
              }`}
            >
              {tab.label}
              {typeof count === "number" && count > 0 ? (
                <span className="ml-1.5 text-[11px] opacity-70">{count}</span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[var(--border-subtle)]">
        {!history ? (
          <p className="px-4 py-10 text-[13px] text-[var(--text-secondary)]">
            Unable to load your earnings right now.
          </p>
        ) : history.rows.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <p className="text-[14px] text-[var(--text-primary)]">
              {status === "all"
                ? "No earnings yet."
                : `Nothing ${EARNING_LABEL[status]?.toLowerCase() ?? status} right now.`}
            </p>
            <p className="mx-auto mt-1 max-w-[30rem] text-[13px] text-[var(--text-secondary)]">
              {status === "all"
                ? "When a review you wrote leads to a purchase, it appears here with exactly how the commission was split."
                : "Try another filter to see the rest of your history."}
            </p>
          </div>
        ) : (
          <ol>
            {history.rows.map((row) => (
              <EarningItem key={row.commission_id} row={row} />
            ))}
          </ol>
        )}
      </div>
    </DashboardScreen>
  );
}

/** The status pill tints 6152:1050 draws, under ink text (paid is not drawn; trust blue). */
const STATUS_TINT: Record<string, string> = {
  pending: "bg-[rgba(250,200,0,0.6)]",
  to_earn: "bg-[rgba(31,175,56,0.3)]",
  paid: "bg-[rgba(55,113,200,0.3)]",
  returned: "bg-[rgba(216,0,39,0.3)]",
};

function EarningItem({ row }: { row: EarningRow }) {
  const when = new Date(`${row.occurred_on}T00:00:00`).toLocaleDateString("en-PH", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      {/* <details> rather than client state: the row expands by keyboard, works
          without JavaScript, and needs no hydration on a money screen.

          Frame 6152:1050, read 2026-09-17: 12px under the rule, the date in
          10px Regular with the status pill (23px, radius 16, 8px sides, 10px
          Regular ink on its tint) at the right; 4px lower an 80px photo at
          radius 16, then 16px in a 233px column — the product in 10px Bold,
          the quote in 12px Regular on one line, and 12px under them the amount
          in 20px SemiBold green with a 12px caret. It was a 56px photo with
          13px SemiBold, 12px italic and 15px Bold. */}
      <details className="group">
        <summary className="flex cursor-pointer list-none flex-col gap-1 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]">
          <span className="flex items-start justify-between gap-2">
            <span className="text-[10px] leading-none text-[var(--text-primary)]">{when}</span>
            {/* The pill carries its own words, so status never depends on colour alone. */}
            <span
              className={`inline-flex h-[23px] shrink-0 items-center rounded-[16px] px-2 text-[10px] leading-none text-[var(--text-primary)] ${
                STATUS_TINT[row.status] ?? "bg-[var(--line-hairline-10)]"
              }`}
            >
              {EARNING_LABEL[row.status] ?? row.status}
            </span>
          </span>

          <span className="flex items-start gap-4">
            <span className="relative block h-20 w-20 shrink-0 overflow-hidden rounded-[16px] bg-[var(--line-hairline-10)]">
              {row.photo_url ? (
                <Image src={row.photo_url} alt="" fill sizes="160px" className="object-cover" />
              ) : null}
            </span>

            <span className="flex min-w-0 max-w-[233px] flex-1 flex-col gap-3">
              <span className="block min-w-0 text-[var(--text-primary)]">
                <span className="block truncate text-[10px] font-bold leading-normal">
                  {row.product_name ?? "Product"}
                </span>
                {row.review_title ? (
                  <span className="block truncate text-[12px] leading-none">
                    &ldquo;{row.review_title}&rdquo;
                  </span>
                ) : null}
              </span>

              <span className="flex items-center gap-1 text-[20px] font-semibold leading-none text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
                {pesoWhole(row.amount)}
                <CaretRight size={12} weight="bold" className="transition-transform group-open:rotate-90" />
              </span>
            </span>
          </span>
        </summary>

        {/* 6152:1042: 358 wide, white, radius 12, a 0 4 2 10% drop shadow, 20px
            padding; Price / Comm. % / Earned as 12px Regular labels at 70% over
            14px Regular values, then the three shares 24px lower in 16px
            SemiBold over 12px Regular labels, 48px apart; the Info glyph 20px
            at the right. */}
        <div className="mx-4 mb-3 rounded-[12px] bg-[var(--surface-card)] p-5 [filter:drop-shadow(0_4px_2px_rgba(0,0,0,0.1))]">
          <dl className="flex flex-wrap items-start gap-x-6 gap-y-2">
            <div>
              <dt className="text-[12px] leading-none text-[rgba(32,32,32,0.7)]">Price</dt>
              <dd className="mt-1 text-[14px] leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {pesoWhole(row.breakdown.gross_amount)}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] leading-none text-[rgba(32,32,32,0.7)]">Comm. %</dt>
              <dd className="mt-1 text-[14px] leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {/* Never derived by dividing the shares: the two are rounded
                    independently and would disagree in the last centavo. */}
                {row.breakdown.commission_rate
                  ? `${Number(row.breakdown.commission_rate)}%`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] leading-none text-[rgba(32,32,32,0.7)]">Earned</dt>
              <dd className="mt-1 text-[14px] leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {/* The commission, not the price: the three shares added up.
                    Rendering gross here would print Price twice. */}
                {pesoWhole(
                  sumPeso(
                    row.breakdown.platform_share,
                    row.breakdown.honesty_fund_share,
                    row.breakdown.reviewer_share,
                  ),
                )}
              </dd>
            </div>
            {/* The frame parks the info affordance at the right edge of the row. */}
            <Info size={20} weight="regular" aria-hidden className="ml-auto mt-1 shrink-0 text-[var(--text-primary)]" />
          </dl>

          <div className="mt-6 flex flex-wrap gap-x-12 gap-y-3">
            <Split label="Bluntly" value={row.breakdown.platform_share} tone="text-[var(--accent-primary)]" />
            <Split label="Honesty Fund" value={row.breakdown.honesty_fund_share} tone="text-[var(--accent-trust)]" />
            <Split label="Yours" value={row.breakdown.reviewer_share} tone="text-[var(--accent-success)]" />
          </div>

          {row.review_id ? (
            <Link
              href={`/reviews/${row.review_id}`}
              className="mt-3 inline-block text-[12px] text-[var(--text-secondary)] underline hover:text-[var(--accent-primary)]"
            >
              Open the review
            </Link>
          ) : null}
        </div>
      </details>
    </li>
  );
}

function Split({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <dd className={`text-[16px] font-semibold leading-none [font-variant-numeric:tabular-nums] ${tone}`}>
        {pesoWhole(value)}
      </dd>
      <dt className="text-[12px] leading-none text-[var(--text-primary)]">{label}</dt>
    </div>
  );
}
