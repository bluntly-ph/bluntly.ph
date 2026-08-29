import {
  CheckCircle,
  Clock,
  Question,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react/dist/ssr";

import type { SchedulerHealth as Health } from "@/lib/moderation";

/**
 * Scheduled maintenance, on the Activity Log.
 *
 * The eight periodic jobs run on an external scheduler, so the only way a
 * moderator can tell the automation is alive is the record each run leaves —
 * and a scheduler that stopped a fortnight ago looks exactly like a healthy one
 * if all you show is "last run: ok". So this shows STANDING, not just history:
 *
 *   healthy    this period has succeeded, or has not come round yet
 *   due        this period is due and has not succeeded, recently
 *   overdue    due, unsucceeded, and well past when it should have run
 *   failed     the most recent attempt at this period failed
 *   never run  no successful execution has ever been recorded
 *
 * None of these claims anything about future execution — they describe what has
 * and has not happened. No payloads, no credentials, and a failure shows an
 * exception class rather than a message, because a message can carry row data
 * into a table people read.
 */

const STATE: Record<string, { label: string; cls: string; Icon: typeof CheckCircle }> = {
  healthy: { label: "Healthy", cls: "text-[var(--accent-success)]", Icon: CheckCircle },
  due: { label: "Due", cls: "text-[var(--accent-trust)]", Icon: Clock },
  overdue: { label: "Overdue", cls: "text-[var(--accent-star)]", Icon: WarningCircle },
  failed: { label: "Failed", cls: "text-[var(--accent-danger)]", Icon: XCircle },
  never_run: { label: "Never run", cls: "text-[var(--text-muted)]", Icon: Question },
};

function ago(iso: string | null): string {
  if (!iso) return "never";
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

  const tasks = health.tasks ?? [];
  const bad = tasks.filter((t) => t.state === "overdue" || t.state === "failed");
  const waiting = tasks.filter((t) => t.state === "never_run");

  const summary =
    bad.length > 0
      ? `${bad.length} task${bad.length === 1 ? "" : "s"} need attention`
      : waiting.length > 0
        ? `${waiting.length} awaiting a first run`
        : "All tasks healthy";

  return (
    <section
      aria-labelledby="scheduler-heading"
      className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="scheduler-heading" className="text-[14px] font-semibold text-[var(--text-primary)]">
          Scheduled maintenance
        </h2>
        <p
          className={`text-[12px] ${
            bad.length > 0 ? "text-[var(--accent-danger)]" : "text-[var(--text-secondary)]"
          }`}
        >
          {summary}
        </p>
      </div>

      <p className="mt-1 max-w-[54rem] text-[12px] text-[var(--text-muted)]">
        These run automatically. A task is judged against its current period, so
        a scheduler that has stopped shows as overdue rather than simply going
        quiet. Moderators can still run one now from its own surface; both paths
        take the same route through the service.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[38rem] border-collapse text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="pb-2 font-medium">Task</th>
              <th className="pb-2 font-medium">State</th>
              <th className="pb-2 font-medium">Period</th>
              <th className="pb-2 font-medium">Last success</th>
              <th className="pb-2 font-medium">Processed</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
              const tone = STATE[t.state] ?? STATE.never_run;
              return (
                <tr key={t.task} className="border-t border-[var(--border-subtle)] text-[13px]">
                  <td className="py-2 font-medium text-[var(--text-primary)]">
                    {t.task.replace(/_/g, " ")}
                    <span className="ml-2 text-[11px] font-normal text-[var(--text-muted)]">
                      {t.cadence}
                    </span>
                  </td>
                  <td className={`py-2 ${tone.cls}`}>
                    <span className="inline-flex items-center gap-1.5">
                      <tone.Icon size={15} weight="fill" />
                      {tone.label}
                      {t.state === "failed" && t.last_run?.failure ? (
                        <span className="text-[12px]">({t.last_run.failure})</span>
                      ) : null}
                    </span>
                  </td>
                  <td className="py-2 font-mono text-[12px] text-[var(--text-secondary)]">
                    {t.period}
                  </td>
                  <td className="py-2 text-[var(--text-secondary)]">
                    {ago(t.last_success_at)}
                  </td>
                  <td className="py-2 [font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                    {t.last_run?.processed ?? (
                      <span className="text-[var(--text-muted)]">&mdash;</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
