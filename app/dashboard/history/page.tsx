import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { CaretRight, Info } from "@phosphor-icons/react/dist/ssr";

import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { requireOnboardedUser } from "@/lib/dal";
import {
  EARNING_LABEL,
  EARNING_TABS,
  EARNING_TONE,
  getEarnings,
  peso,
  pesoWhole,
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
  await requireOnboardedUser();
  const status = (await searchParams).status ?? "all";
  const history = await getEarnings(status);

  return (
    <DashboardScreen
      heroHeight={300}
      hero={
        <div className="px-4 pb-14 pt-2">
          {/* The frame's floating card, straddling the gradient. */}
          <div className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-5 py-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[26px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                  {history ? peso(history.all_time) : peso(0)}
                </p>
                <p className="mt-1.5 text-[12px] text-[var(--text-secondary)]">
                  Est. All time income
                </p>
              </div>
              <span className="shrink-0 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-3.5 py-1.5 text-[12px] font-semibold text-[var(--text-on-brand)]">
                Historical Bill
              </span>
            </div>
          </div>
        </div>
      }
    >
      {/* Tabs are links, not client state: the filter belongs in the URL so a
          reviewer can share or reload a filtered view, and back/forward work. */}
      <nav aria-label="Filter earnings" className="flex gap-5 overflow-x-auto px-4 pb-1">
        {EARNING_TABS.map((tab) => {
          const active = tab.key === status;
          const count = history?.counts?.[tab.key];
          return (
            <Link
              key={tab.key}
              href={tab.key === "all" ? "/dashboard/history" : `/dashboard/history?status=${tab.key}`}
              scroll={false}
              aria-current={active ? "page" : undefined}
              className={`shrink-0 border-b-2 pb-2 text-[13px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                active
                  ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
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

function EarningItem({ row }: { row: EarningRow }) {
  const when = new Date(`${row.occurred_on}T00:00:00`).toLocaleDateString("en-PH", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <li className="border-b border-[var(--border-subtle)]">
      {/* <details> rather than client state: the row expands by keyboard, works
          without JavaScript, and needs no hydration on a money screen. */}
      <details className="group">
        <summary className="flex cursor-pointer list-none items-start gap-3 px-4 py-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]">
          <span className="relative block h-14 w-14 shrink-0 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--line-hairline-10)]">
            {row.photo_url ? (
              <Image src={row.photo_url} alt="" fill sizes="112px" className="object-cover" />
            ) : null}
          </span>

          <span className="min-w-0 flex-1">
            <span className="flex items-start justify-between gap-2">
              <span className="min-w-0">
                <span className="block text-[11px] text-[var(--text-muted)]">{when}</span>
                <span className="mt-0.5 block truncate text-[13px] font-semibold text-[var(--text-primary)]">
                  {row.product_name ?? "Product"}
                </span>
              </span>
              {/* The badge carries its own words, so status never depends on
                  colour alone. */}
              <span
                className={`shrink-0 rounded-[var(--radius-pill)] px-2.5 py-1 text-[11px] font-semibold ${
                  EARNING_TONE[row.status] ?? "bg-[var(--surface-app)] text-[var(--text-secondary)]"
                }`}
              >
                {EARNING_LABEL[row.status] ?? row.status}
              </span>
            </span>

            {row.review_title ? (
              <span className="mt-1 block truncate text-[12px] italic text-[var(--text-secondary)]">
                &ldquo;{row.review_title}&rdquo;
              </span>
            ) : null}

            <span className="mt-1.5 flex items-center gap-1 text-[15px] font-bold text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
              {pesoWhole(row.amount)}
              <CaretRight
                size={12}
                weight="bold"
                className="transition-transform group-open:rotate-90"
              />
            </span>
          </span>
        </summary>

        <div className="mx-4 mb-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 shadow-[var(--shadow-hairline-inset)]">
          <dl className="flex flex-wrap items-start gap-x-8 gap-y-2">
            <div>
              <dt className="text-[11px] text-[var(--text-muted)]">Price</dt>
              <dd className="text-[13px] font-medium text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {pesoWhole(row.breakdown.gross_amount)}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-[var(--text-muted)]">Comm. %</dt>
              <dd className="text-[13px] font-medium text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {/* Never derived by dividing the shares: the two are rounded
                    independently and would disagree in the last centavo. */}
                {row.breakdown.commission_rate
                  ? `${Number(row.breakdown.commission_rate)}%`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]">
                Earned
                <Info size={12} weight="regular" />
              </dt>
              <dd className="text-[13px] font-medium text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {pesoWhole(row.breakdown.gross_amount)}
              </dd>
            </div>
          </dl>

          <div className="mt-3 flex flex-wrap gap-x-8 gap-y-3 border-t border-[var(--border-subtle)] pt-3">
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
    <div>
      <dd className={`text-[15px] font-bold [font-variant-numeric:tabular-nums] ${tone}`}>
        {pesoWhole(value)}
      </dd>
      <dt className="mt-0.5 text-[11px] text-[var(--text-secondary)]">{label}</dt>
    </div>
  );
}
