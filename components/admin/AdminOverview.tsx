import Link from "next/link";

import { pesoWhole } from "@/lib/dashboard";

/**
 * The Overview screen's cards, built to the approved Admin Page frame.
 *
 * Four headline counts, a recent-activity feed and a queue breakdown. Every
 * figure is queried; nothing is a placeholder, and the design's implied
 * comparison ("+3 from yesterday") is actually computed rather than written in.
 */

export type AdminOverviewData = {
  queue_total: number;
  high_priority: number;
  approved_today: number;
  approved_delta: number;
  pending_affiliate: number;
  honesty_fund_pool: string;
  honesty_fund_month: string;
  urgent: number;
  breakdown: { label: string; count: number }[];
  affiliate: {
    lifecycle: { label: string; count: number }[];
    settlement: { label: string; count: number }[];
    recognised_amount: string;
    reversed_amount: string;
    unrecovered_amount: string;
    has_data: boolean;
  };
  activity: {
    action: string;
    actor: string | null;
    target_ref: string | null;
    at: string;
  }[];
  /** Sections the backend could not compute for this request. */
  unavailable?: string[];
  /** Exception class per failed section, e.g. "affiliate: LookupError". */
  diagnostics?: string[];
};

/** Bar colours, in the frame's order. Each bar also states its own number, so
 *  colour is never the only thing carrying the value. */
const BAR_COLOR = [
  "bg-[var(--accent-primary)]",
  "bg-[var(--accent-danger)]",
  "bg-[var(--accent-trust)]",
  "bg-[var(--accent-success)]",
];

/**
 * Activity colour by outcome, matching the frame's tinted rows.
 *
 * The frame washes each row in its outcome's colour and puts a dot in it. Both
 * are kept: the wash carries the glance, the dot survives a greyscale print,
 * and the row's own words say what happened regardless of either.
 */
function toneFor(action: string): { dot: string; wash: string } {
  if (action.startsWith("approve") || action === "publish")
    return { dot: "bg-[var(--accent-success)]", wash: "from-[var(--accent-success)]/12" };
  if (action.startsWith("reject") || action === "remove" || action === "unpublish")
    return { dot: "bg-[var(--accent-danger)]", wash: "from-[var(--accent-danger)]/12" };
  if (action.startsWith("affiliate"))
    return { dot: "bg-[var(--accent-trust)]", wash: "from-[var(--accent-trust)]/12" };
  return { dot: "bg-[var(--accent-primary)]", wash: "from-[var(--accent-primary)]/12" };
}

const ACTION_LABEL: Record<string, string> = {
  approve: "Approved Review",
  reject: "Rejected Review",
  publish: "Published Review",
  unpublish: "Unpublished Review",
  remove: "Removed Review",
  affiliate_link_attach: "Affiliate Link Generated",
  affiliate_link_revoke: "Affiliate Link Revoked",
  csv_import: "Commission Import",
  payout: "Payout",
  honesty_fund_distribution: "Honesty Fund Distribution",
  escalate: "Escalated",
};

function relative(iso: string): string {
  const then = new Date(iso).getTime();
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function AdminOverview({ data }: { data: AdminOverviewData | null }) {
  if (!data) {
    return (
      <p className="text-[14px] text-[var(--text-secondary)]">
        Unable to load the overview right now.
      </p>
    );
  }

  // A panel failing is not the screen failing. The backend names what it could
  // not compute, so the moderator is told which part is missing and still gets
  // everything that worked.
  const missing = data.unavailable ?? [];

  const month = new Date(`${data.honesty_fund_month}T00:00:00`).toLocaleDateString(
    "en-PH",
    { month: "long", year: "numeric" },
  );

  return (
    <>
      {missing.length > 0 ? (
        <p
          role="status"
          className="mb-4 rounded-[var(--radius-sm)] bg-[var(--accent-star)]/10 px-4 py-3 text-[13px] text-[var(--text-primary)]"
        >
          {missing.includes("overview")
            ? "The headline counts, activity feed and queue breakdown could not be loaded, so the figures below read zero. "
            : ""}
          {missing.includes("affiliate")
            ? "The affiliate ledger could not be loaded. "
            : ""}
          Everything else on this page is live.
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Queue Total"
          value={String(data.queue_total)}
          note={
            data.high_priority > 0
              ? `${data.high_priority} high priority`
              : "Nothing flagged"
          }
          tone={data.high_priority > 0 ? "danger" : "muted"}
        />
        <Kpi
          label="Approved Today"
          value={String(data.approved_today)}
          // Signed and computed, not decorative: it says nothing when nothing
          // changed rather than claiming an increase.
          note={
            data.approved_delta === 0
              ? "Same as yesterday"
              : `${data.approved_delta > 0 ? "+" : ""}${data.approved_delta} from yesterday`
          }
          tone={data.approved_delta > 0 ? "success" : "muted"}
        />
        <Kpi
          label="Pending Affiliate"
          value={String(data.pending_affiliate)}
          note={data.pending_affiliate > 0 ? "Links to generate" : "All generated"}
          tone={data.pending_affiliate > 0 ? "trust" : "muted"}
        />
        <Kpi
          label="Honesty Fund"
          value={pesoWhole(data.honesty_fund_pool)}
          note={month}
          tone="muted"
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_26rem]">
        <section
          aria-labelledby="recent-activity-heading"
          className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
        >
          <h2
            id="recent-activity-heading"
            className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]"
          >
            Recent activity
          </h2>

          {data.activity.length === 0 ? (
            <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
              Nothing has happened yet.
            </p>
          ) : (
            <ul className="mt-4 flex flex-col gap-2.5">
              {data.activity.map((item, i) => {
                const tone = toneFor(item.action);
                return (
                <li
                  key={`${item.action}-${item.at}-${i}`}
                  className={`flex items-start gap-3 rounded-[var(--radius-sm)] bg-gradient-to-r ${tone.wash} to-transparent px-3 py-2.5`}
                >
                  <span
                    aria-hidden="true"
                    className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tone.dot}`}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-[14px] font-medium text-[var(--text-primary)]">
                      {ACTION_LABEL[item.action] ?? item.action.replace(/_/g, " ")}
                    </span>
                    <span className="mt-0.5 block text-[12px] text-[var(--text-secondary)]">
                      {/* Actions the scheduler took have no moderator. */}
                      {item.actor ?? "System"}
                      <span className="mx-1.5 opacity-50">·</span>
                      {relative(item.at)}
                    </span>
                  </span>
                </li>
                );
              })}
            </ul>
          )}

          <Link
            href="/moderate#queue"
            className="mt-4 inline-block text-[13px] text-[var(--text-secondary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            See more...
          </Link>
        </section>

        <section
          aria-labelledby="queue-breakdown-heading"
          className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
        >
          <h2
            id="queue-breakdown-heading"
            className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]"
          >
            Queue breakdown
          </h2>

          {/* The categories overlap on purpose — one review can be both a
              first submission and a new product — so this is a set of
              independent bars rather than a stacked one, which would imply
              they partition the queue. */}
          <dl className="mt-4 flex flex-col gap-4">
            {data.breakdown.map((bar, i) => {
              const max = Math.max(...data.breakdown.map((b) => b.count), 1);
              return (
                <div key={bar.label}>
                  <div className="flex items-baseline justify-between">
                    <dt className="text-[14px] text-[var(--text-primary)]">
                      {bar.label}
                    </dt>
                    <dd className="text-[14px] font-semibold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                      {bar.count}
                    </dd>
                  </div>
                  <div
                    aria-hidden="true"
                    className="mt-1.5 h-2 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-app)]"
                  >
                    <div
                      className={`h-full rounded-[var(--radius-pill)] ${BAR_COLOR[i % BAR_COLOR.length]}`}
                      style={{ width: `${(bar.count / max) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </dl>
        </section>
      </div>

      <AffiliateLedger data={data.affiliate} />
    </>
  );
}

/**
 * The affiliate ledger, on two separate axes.
 *
 * This is MONEY analytics and sits apart from the request analytics elsewhere
 * on this console on purpose — they are different subjects with different
 * sources, and putting them in one card would invite reading a traffic spike
 * as revenue.
 *
 * Lifecycle and settlement are never summed together: a completed order can be
 * unearned (nobody to attribute it to) and a returned one can be paid (the
 * return landed after payout), so a single combined bar would imply a
 * progression that does not exist.
 */
function AffiliateLedger({
  data,
}: {
  data: AdminOverviewData["affiliate"];
}) {
  return (
    <section
      aria-labelledby="affiliate-ledger-heading"
      className="mt-5 rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
    >
      <h2
        id="affiliate-ledger-heading"
        className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]"
      >
        Affiliate ledger
      </h2>

      {!data.has_data ? (
        <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
          No affiliate transactions imported yet. Import a Shopee or Lazada
          export to populate this.
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <CountRow title="Order lifecycle" bars={data.lifecycle} />
            <CountRow title="Settlement" bars={data.settlement} />
          </div>

          <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3 border-t border-[var(--border-subtle)] pt-4">
            <Money label="Recognised" value={data.recognised_amount} />
            <Money label="Reversed" value={data.reversed_amount} />
            {/* Surfaced rather than buried: this is money the platform
                absorbed because a return arrived after payout, and it has to
                be reconciled by someone. */}
            <Money label="Absorbed (unrecovered)" value={data.unrecovered_amount} />
          </dl>
        </>
      )}
    </section>
  );
}

function CountRow({
  title,
  bars,
}: {
  title: string;
  bars: { label: string; count: number }[];
}) {
  const total = bars.reduce((a, b) => a + b.count, 0) || 1;
  return (
    <div>
      <p className="text-[13px] font-semibold text-[var(--text-primary)]">{title}</p>
      <dl className="mt-3 flex flex-col gap-3">
        {bars.map((bar, i) => (
          <div key={bar.label}>
            <div className="flex items-baseline justify-between">
              <dt className="text-[13px] text-[var(--text-secondary)]">{bar.label}</dt>
              <dd className="text-[13px] font-semibold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                {bar.count}
              </dd>
            </div>
            <div
              aria-hidden="true"
              className="mt-1 h-1.5 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-app)]"
            >
              <div
                className={`h-full rounded-[var(--radius-pill)] ${BAR_COLOR[i % BAR_COLOR.length]}`}
                style={{ width: `${(bar.count / total) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Money({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dd className="text-[18px] font-bold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {pesoWhole(value)}
      </dd>
      <dt className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{label}</dt>
    </div>
  );
}

function Kpi({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone: "danger" | "success" | "trust" | "muted";
}) {
  const noteColor = {
    danger: "text-[var(--accent-danger)]",
    success: "text-[var(--accent-success)]",
    trust: "text-[var(--accent-trust)]",
    muted: "text-[var(--text-secondary)]",
  }[tone];

  return (
    <div className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <p className="text-[14px] text-[var(--text-secondary)]">{label}</p>
      <p className="mt-1 text-[34px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {value}
      </p>
      <p className={`mt-2 text-[13px] ${noteColor}`}>{note}</p>
    </div>
  );
}
