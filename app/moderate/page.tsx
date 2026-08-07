import type { Metadata } from "next";

import { ModerationQueue } from "@/components/moderation/ModerationQueue";
import { ReportQueue } from "@/components/moderation/ReportQueue";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireRole } from "@/lib/dal";
import { getQueue, getReports } from "@/lib/moderation";

export const metadata: Metadata = {
  title: "Moderation — bluntly",
};

export default async function ModeratePage() {
  // Redirects: to /login if signed out, to / if not a moderator.
  const me = await requireRole("moderator");
  const [{ pending, edited }, reports] = await Promise.all([
    getQueue(),
    getReports(),
  ]);

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[52rem] flex-1 px-6 py-8 lg:py-10">
        <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
          Moderation queue
        </h1>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          {pending.length} review{pending.length === 1 ? "" : "s"} awaiting review.
          Approve with an affiliate link to monetize, publish without one, or reject.
        </p>

        <div className="mt-6">
          <ModerationQueue initial={pending} />
        </div>

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
      </main>
      <SiteFooter />
    </div>
  );
}
