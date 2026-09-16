import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

// A Client Component, imported directly. `next/dynamic` with `ssr: false` is
// not permitted in a Server Component in this version, and it would buy
// nothing here: Next already splits client bundles per route.
import { RequestDistribution } from "@/components/analytics/RequestDistribution";
import { AdminOverview } from "@/components/admin/AdminOverview";
import { getAdminOverview } from "@/lib/moderation";

export const metadata: Metadata = {
  title: "Overview — bluntly admin",
};

/**
 * The Overview landing screen.
 *
 * Built to frame 5017:1738, which was deleted from the Figma file before
 * 2026-09-16 and has no replacement — the file's only surviving admin frames
 * are the sidebar and the review queue (see AdminShell). This screen therefore
 * stands on its last reading, and a Figma comparison of it is not available.
 *
 * It is summary and intelligence only. The full review queue used to live
 * underneath it, which made the queue reachable solely by scrolling the
 * overview — the two are separate screens in the design and are separate
 * routes here. The Queue Breakdown now navigates into the queue instead of
 * being a read-only bar chart.
 */
export default async function ModerateOverviewPage() {
  const overview = await getAdminOverview();

  return (
    <>
      <AdminOverview data={overview} />

      <section aria-labelledby="traffic-heading" className="mt-6">
        <h2 id="traffic-heading" className="sr-only">
          Where requests come from
        </h2>
        <RequestDistribution />
        <p className="mt-2 text-[12px] text-[var(--text-muted)]">
          <Link
            href="/moderate/analytics"
            className="inline-flex items-center gap-1 underline hover:text-[var(--accent-primary)]"
          >
            Open the full geography view
            <ArrowRight size={12} weight="bold" />
          </Link>
        </p>
      </section>
    </>
  );
}
