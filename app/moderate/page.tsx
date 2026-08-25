import type { Metadata } from "next";

// A Client Component, imported directly. `next/dynamic` with `ssr: false` is
// not permitted in a Server Component in this version, and it would buy
// nothing here: Next already splits client bundles per route, so this panel
// and its inline map ship only to /moderate and never to the landing page or
// the feed. Verified by the route's First Load JS in the build output.
import { RequestDistribution } from "@/components/analytics/RequestDistribution";
import { AdminOverview } from "@/components/admin/AdminOverview";
import { AdminShell } from "@/components/admin/AdminShell";
import { ModerationQueue } from "@/components/moderation/ModerationQueue";
import { ReportQueue } from "@/components/moderation/ReportQueue";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireRole } from "@/lib/dal";
import { getAdminOverview, getQueue, getReports } from "@/lib/moderation";

export const metadata: Metadata = {
  title: "Moderation — bluntly",
};


export default async function ModeratePage() {
  // Redirects: to /login if signed out, to / if not a moderator.
  const me = await requireRole("moderator");
  const [{ pending, edited }, reports, overview] = await Promise.all([
    getQueue(),
    getReports(),
    getAdminOverview(),
  ]);

  return (
    <AdminShell
      active="Overview"
      title="Overview"
      urgent={overview?.urgent ?? 0}
      moderator={{
        name: me.display_name ?? me.username ?? "Moderator",
        role: me.role ?? "moderator",
      }}
    >
      {/* Below `lg` the sidebar is hidden, so the site header is what gives a
          moderator a way out of the console on a phone. */}
      <div className="mb-4 lg:hidden">
        <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      </div>

      <AdminOverview data={overview} />

      <div className="mt-10">
        <h2 id="queue" className="scroll-mt-6 text-[20px] font-bold text-[var(--text-primary)]">
          Review queue
        </h2>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          {pending.length} review{pending.length === 1 ? "" : "s"} awaiting review.
          Approve with an affiliate link to monetize, publish without one, or reject.
        </p>

        <section className="mt-6">
          {/* The pending queue had no heading of its own, so its card titles
              (h3) followed the page h1 directly and skipped a level. The other
              two sections already carry an h2; this gives the first one the
              same structure rather than demoting the cards. */}
          <h2 className="sr-only">Reviews awaiting moderation</h2>
          <ModerationQueue initial={pending} />
        </section>

        <section className="mt-10">
          <RequestDistribution />
        </section>

        <section className="mt-10">
          <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
            Community reports
          </h2>
          <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
            {reports.length === 0
              ? "Nothing has been reported."
              : "Flagged by readers, most-reported first. Act on the review itself."}
          </p>
          <div className="mt-4">
            <ReportQueue items={reports} />
          </div>
        </section>

        {edited.length > 0 ? (
          <section className="mt-10">
            <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
              Edited since monetized
            </h2>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
              These were changed after their affiliate link was attached — re-check them.
            </p>
            <div className="mt-4">
              <ModerationQueue initial={edited} />
            </div>
          </section>
        ) : null}
      </div>

      <SiteFooter />
    </AdminShell>
  );
}
