import { CheckCircle, Clock, WarningCircle, XCircle } from "@phosphor-icons/react/dist/ssr";

import type { SchedulerHealth as Health } from "@/lib/moderation";

/**
 * Scheduled maintenance, on the Activity Log.
 *
 * The eight periodic jobs run on an external scheduler, so the only way a
 * moderator can tell the automation is alive is the record each run leaves.
 * This is that record, and it is deliberately small: task, outcome, when, and
 * how much it processed. No payloads, no credentials, and a failure shows an
 * exception class rather than a message, because a message can carry row data
 * into a table people read.
 *
 * "Never run" is the row that matters most on a fresh deployment: a job that
 * has never executed looks identical to a healthy one if you only list
 * successes.
 */

const TONE: Record<string, { cls: string; Icon: typeof CheckCircle }> = {
  ok: { cls: "text-[var(--accent-success)]", Icon: CheckCircle },
  skipped: { cls: "text-[var(--text-muted)]", Icon: Clock },
  locked: { cls: "text-[var(--accent-star)]", Icon: WarningCircle },
  failed: { cls: "text-[var(--accent-danger)]", Icon: XCircle },
};

function ago(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${Math.floor(secs)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function SchedulerHealth({ health }: { health: Health | null }) {
  if (!health) {
    return (
      <section
        aria-labelledby="scheduler-heading"
        className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
      >
        <h2 id="scheduler-heading" className="text-[14px] font-semibold text-[var(--text-primary)]">
          Scheduled maintenance
        </h2>
        <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
          Unable to load the scheduler record right now.
        </p>
      </section>
    );
  }

  const failing = health.latest.filter((r) => r.status === "failed");

  return (
    <section
      aria-labelledby="scheduler-heading"
      className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="scheduler-heading" className="text-[14px] font-semibold text-[var(--text-primary)]">
          Scheduled maintenance
        </h2>
        <p className="text-[12px] text-[var(--text-secondary)]">
          {failing.length > 0
            ? `${failing.length} task${failing.length === 1 ? "" : "s"} failing`
            : health.never_run.length > 0
              ? `${health.never_run.length} not yet run`
              : "All tasks healthy"}
        </p>
      </div>

      <p className="mt-1 max-w-[52rem] text-[12px] text-[var(--text-muted)]">
        These run automatically. A moderator can still run one now from its own
        surface, and both paths take the same route through the service.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="pb-2 font-medium">Task</th>
              <th className="pb-2 font-medium">Last run</th>
              <th className="pb-2 font-medium">Processed</th>
              <th className="pb-2 font-medium">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {health.latest.map((r) => {
              const tone = TONE[r.status] ?? TONE.skipped;
              return (
                <tr key={r.task} className="border-t border-[var(--border-subtle)] text-[13px]">
                  <td className="py-2 font-medium text-[var(--text-primary)]">
                    {r.task.replace(/_/g, " ")}
                  </td>
                  <td className="py-2 text-[var(--text-secondary)]">{ago(r.started_at)}</td>
                  <td className="py-2 [font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                    {r.processed ?? <span className="text-[var(--text-muted)]">&mdash;</span>}
                  </td>
                  <td className={`py-2 ${tone.cls}`}>
                    <span className="inline-flex items-center gap-1.5">
                      <tone.Icon size={15} weight="fill" />
                      {r.status === "failed" && r.failure ? r.failure : r.status}
                      {r.detail ? (
                        <span className="text-[12px] text-[var(--text-muted)]">({r.detail})</span>
                      ) : null}
                    </span>
                  </td>
                </tr>
              );
            })}

            {health.never_run.map((task) => (
              <tr key={task} className="border-t border-[var(--border-subtle)] text-[13px]">
                <td className="py-2 font-medium text-[var(--text-primary)]">
                  {task.replace(/_/g, " ")}
                </td>
                <td className="py-2 text-[var(--text-muted)]">never</td>
                <td className="py-2 text-[var(--text-muted)]">&mdash;</td>
                <td className="py-2 text-[var(--text-muted)]">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock size={15} />
                    awaiting first run
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
