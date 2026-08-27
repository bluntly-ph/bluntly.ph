import type { Metadata } from "next";
import Link from "next/link";

import { getAdminOverview } from "@/lib/moderation";

export const metadata: Metadata = { title: "Affiliate links — bluntly admin" };

/**
 * The affiliate ledger, on two axes that are never summed together.
 *
 * Lifecycle is what the marketplace says happened to the order; settlement is
 * what our own ledger did about it. A `completed` order can be `not_earned`
 * (nobody to attribute it to) and a `returned` one can be `paid` (the return
 * arrived after payout, which the platform absorbs), so one combined bar would
 * assert a progression that does not exist.
 */
export default async function AffiliateLinksPage() {
  const overview = await getAdminOverview();
  const a = overview?.affiliate;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pb-2">
      <div>
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Affiliate ledger</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          {overview?.pending_affiliate
            ? `${overview.pending_affiliate} approved review${overview.pending_affiliate === 1 ? "" : "s"} still need a link generating.`
            : "Every approved review has its affiliate link."}
        </p>
      </div>

      {!a || !a.has_data ? (
        <p className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-6 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-card)]">
          No affiliate transactions have been imported yet. Import a Shopee or Lazada
          export to populate this ledger.
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Money label="Recognised" value={a.recognised_amount} />
            <Money label="Reversed" value={a.reversed_amount} tone="danger" />
            <Money
              label="Absorbed"
              value={a.unrecovered_amount}
              hint="Returned after payout. The platform absorbs it; no reviewer is put into debt."
            />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Axis
              title="Order lifecycle"
              caption="What the marketplace says happened to the order."
              bars={a.lifecycle}
            />
            <Axis
              title="Settlement"
              caption="What our ledger did about it."
              bars={a.settlement}
            />
          </div>
        </>
      )}

      <p className="text-[12px] text-[var(--text-muted)]">
        Links are attached per review from the{" "}
        <Link href="/moderate/review-queue" className="underline hover:text-[var(--accent-primary)]">
          review queue
        </Link>
        , where the sub-ID that makes a commission attributable is generated with them.
      </p>
    </div>
  );
}

function Money({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "danger";
  hint?: string;
}) {
  return (
    <div
      title={hint}
      className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-5 py-4 shadow-[var(--shadow-card)]"
    >
      <p className="text-[12px] text-[var(--text-secondary)]">{label}</p>
      <p
        className={`mt-1 text-[24px] font-bold [font-variant-numeric:tabular-nums] ${
          tone === "danger" ? "text-[var(--accent-danger)]" : "text-[var(--text-primary)]"
        }`}
      >
        &#8369;{Number(value).toLocaleString("en-PH", { minimumFractionDigits: 2 })}
      </p>
    </div>
  );
}

function Axis({
  title,
  caption,
  bars,
}: {
  title: string;
  caption: string;
  bars: { label: string; count: number }[];
}) {
  const max = Math.max(...bars.map((b) => b.count), 1);
  return (
    <section className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">{caption}</p>
      <dl className="mt-4 flex flex-col gap-3">
        {bars.map((b) => (
          <div key={b.label}>
            <div className="flex items-baseline justify-between text-[13px]">
              <dt className="text-[var(--text-primary)]">{b.label}</dt>
              <dd className="[font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                {b.count}
              </dd>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-[var(--line-hairline-10)]">
              <div
                className="h-full rounded-full bg-[var(--accent-primary)]"
                style={{ width: `${Math.round((b.count / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
    </section>
  );
}
