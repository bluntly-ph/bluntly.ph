import type { Metadata } from "next";

import { RequestDistribution } from "@/components/analytics/RequestDistribution";

export const metadata: Metadata = {
  title: "Where requests come from — bluntly admin",
};

/**
 * The expanded geography view.
 *
 * The owner's question was "where can moderators see the globe for what
 * country does what" — on the old single page the panel was buried below the
 * whole review queue. It now has its own destination, and the Overview links
 * here.
 *
 * Visitor geography and the serving edge are different facts and are labelled
 * separately: a reader in Parañaque served from Singapore is normal, and
 * reading "SIN" as the reader's city would be wrong.
 */
export default function ModerateAnalyticsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 pb-2">
      <div>
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
          Where requests come from
        </h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          Aggregate page requests by approximate location, kept for 90 days. No IP
          addresses and no identities are stored, and no row can be joined back to a
          person &mdash; the edge resolves the address to a place before the request
          reaches the application.
        </p>
      </div>

      <RequestDistribution />

      <section className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
          Reading this panel
        </h3>
        <dl className="mt-3 grid gap-x-8 gap-y-3 sm:grid-cols-2">
          <div>
            <dt className="text-[12px] font-semibold text-[var(--text-primary)]">Count</dt>
            <dd className="text-[13px] text-[var(--text-secondary)]">
              Page requests in the selected window. Not API calls, not prefetches, not
              assets.
            </dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold text-[var(--text-primary)]">RPS</dt>
            <dd className="text-[13px] text-[var(--text-secondary)]">
              Requests divided by the seconds actually covered by data &mdash; never the
              nominal window, so a partly-collected day is not reported as a slow one.
            </dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold text-[var(--text-primary)]">
              Visitor location
            </dt>
            <dd className="text-[13px] text-[var(--text-secondary)]">
              The country, region and city the edge resolved for the reader. This is the
              answer to &ldquo;where are my requests coming from&rdquo;.
            </dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold text-[var(--text-primary)]">
              Served via
            </dt>
            <dd className="text-[13px] text-[var(--text-secondary)]">
              The edge location that served it &mdash; infrastructure context only. A
              reader in the Philippines is normally served from Singapore, and
              &ldquo;SIN&rdquo; is not where they are.
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
