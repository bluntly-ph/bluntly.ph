import type { Metadata } from "next";

import { getAdminOverview } from "@/lib/moderation";

export const metadata: Metadata = { title: "Honesty Fund — bluntly admin" };

/**
 * The Honesty Fund pool for the current Manila cycle.
 *
 * Distribution is a scheduled operation, not a button: it runs over the closed
 * cycle rather than on demand, so there is no "distribute now" control here to
 * click. Showing one would imply a capability the product deliberately does not
 * give a moderator.
 */
export default async function HonestyFundPage() {
  const overview = await getAdminOverview();
  const month = overview
    ? new Date(`${overview.honesty_fund_month}T00:00:00`).toLocaleDateString("en-PH", {
        month: "long",
        year: "numeric",
      })
    : "";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pb-2">
      <div>
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Honesty Fund</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          Thirty per cent of every commission is pooled here and shared out across the
          cycle&rsquo;s eligible contributors.
        </p>
      </div>

      <div className="max-w-[22rem] rounded-[var(--radius-md)] bg-[var(--surface-card)] px-5 py-4 shadow-[var(--shadow-card)]">
        <p className="text-[12px] text-[var(--text-secondary)]">Pool this cycle</p>
        <p className="mt-1 text-[30px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
          &#8369;
          {Number(overview?.honesty_fund_pool ?? 0).toLocaleString("en-PH", {
            minimumFractionDigits: 2,
          })}
        </p>
        <p className="mt-1.5 text-[12px] text-[var(--text-muted)]">{month}</p>
      </div>

      <section className="max-w-[52rem] rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
          How this cycle closes
        </h3>
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          The cycle is a Manila calendar month. A commission belongs to the month it was
          recognised in, which is why the pool and the commissions that fill it always
          agree about which month they are in. Distribution runs as a scheduled operation
          over the closed cycle &mdash; there is no on-demand control here, because a
          moderator triggering a payout run by hand is not how the product works.
        </p>
      </section>
    </div>
  );
}
