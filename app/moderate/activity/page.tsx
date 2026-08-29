import type { Metadata } from "next";
import Link from "next/link";

import { SchedulerHealth } from "@/components/admin/SchedulerHealth";
import { getActivityLog, getSchedulerHealth } from "@/lib/moderation";

export const metadata: Metadata = { title: "Activity log — bluntly admin" };

/**
 * The full moderation audit log.
 *
 * The Overview's feed shows five entries and deliberately omits `receipt_view`,
 * which records a moderator opening someone's proof of purchase. That omission
 * is about not advertising private-evidence access as routine activity in a
 * dashboard; the audit log itself is where the complete record belongs.
 */
export default async function ActivityLogPage() {
  // Independent of each other, so they are not serialised.
  const [log, scheduler] = await Promise.all([
    getActivityLog(100),
    getSchedulerHealth(),
  ]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* The automation's record sits above the human one: it is the only way
          to tell that scheduled maintenance is alive, and a job that has never
          run looks identical to a healthy one unless it is listed. */}
      <div className="shrink-0 pb-4">
        <SchedulerHealth health={scheduler} />
      </div>

      <div className="shrink-0 pb-3">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Activity log</h2>
        <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
          {log
            ? `${log.total} recorded action${log.total === 1 ? "" : "s"}, newest first.`
            : "Unable to load the activity log right now."}
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        <table className="w-full min-w-[40rem] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Actor</th>
              <th className="px-4 py-3 font-medium">Target</th>
              <th className="px-4 py-3 font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {!log || log.rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                  {log ? "Nothing has been recorded yet." : "Unable to load the log."}
                </td>
              </tr>
            ) : (
              log.rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border-subtle)] text-[13px]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">
                    {row.action.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                    {row.actor ?? <span className="text-[var(--text-muted)]">System</span>}
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                    {row.target_ref && row.target_type === "review" ? (
                      <Link
                        href={`/reviews/${row.target_ref}`}
                        className="font-mono text-[12px] underline hover:text-[var(--accent-primary)]"
                      >
                        {row.target_ref.slice(0, 8)}
                      </Link>
                    ) : row.target_ref ? (
                      <span className="font-mono text-[12px]">{row.target_ref.slice(0, 8)}</span>
                    ) : (
                      <span className="text-[var(--text-muted)]">&mdash;</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-[12px] text-[var(--text-muted)]">
                    {new Date(row.at).toLocaleString("en-PH", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
