import Link from "next/link";
import { Flag, LinkSimple, Warning } from "@phosphor-icons/react/dist/ssr";

import { REPORT_REASON_LABELS, type ReportItem } from "@/lib/moderation";

/**
 * Reporter-supplied, moderator-clicked — the worst combination for an `href`.
 * React does not sanitize `href`, so a `javascript:` URL would execute in the
 * moderator's session. The API rejects non-web schemes on write; this repeats
 * the check on read so rows written before that validation existed (or by any
 * other writer) can't turn into a click-to-execute link.
 */
function safeHref(url: string | null): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : null;
}

/**
 * Community reports awaiting a moderator. Read-only: acting on a report is done
 * on the review itself (publish / reject / remove), so this surface exists to
 * route attention rather than to duplicate those controls.
 *
 * Reports are grouped by target so a review flagged by five people is one card
 * carrying five reasons, not five cards competing for the same decision.
 */
export function ReportQueue({ items }: { items: ReportItem[] }) {
  if (items.length === 0) {
    return (
      <p className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-8 text-center text-[13px] text-[var(--text-muted)] shadow-[var(--shadow-hairline-inset)]">
        No open reports.
      </p>
    );
  }

  const groups = new Map<string, ReportItem[]>();
  for (const item of items) {
    const key = item.report.target_ref ?? item.report.id;
    const bucket = groups.get(key);
    if (bucket) bucket.push(item);
    else groups.set(key, [item]);
  }

  // Most-reported first — a pile-on is the strongest triage signal available.
  const ordered = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <ul className="flex flex-col gap-4">
      {ordered.map(([key, group]) => {
        const target = group[0].target;
        const count = group[0].target_report_count || group.length;
        const contested = count >= 3;
        return (
          <li
            key={key}
            className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-[var(--text-primary)]">
                  {target?.title ?? "Reported content"}
                </p>
                <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">
                  {target
                    ? target.is_published
                      ? "Published"
                      : "Not published"
                    : "Target unavailable"}
                </p>
              </div>
              <span
                className={`inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-[12px] font-semibold ${
                  contested
                    ? "bg-[color-mix(in_srgb,var(--accent-danger)_14%,transparent)] text-[var(--accent-danger)]"
                    : "bg-[var(--surface-app)] text-[var(--text-secondary)]"
                }`}
              >
                {contested ? <Warning size={14} weight="fill" /> : <Flag size={14} />}
                {count} report{count === 1 ? "" : "s"}
              </span>
            </div>

            <ul className="mt-4 flex flex-col gap-3 border-t border-[var(--border-subtle)] pt-3">
              {group.map((item) => (
                <li key={item.report.id} className="text-[13px]">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium text-[var(--text-primary)]">
                      {REPORT_REASON_LABELS[item.report.reason ?? ""] ??
                        item.report.reason ??
                        "Unspecified"}
                    </span>
                    <span className="text-[12px] text-[var(--text-muted)]">
                      by{" "}
                      {item.reporter?.display_name ??
                        item.reporter?.username ??
                        "a member"}{" "}
                      &middot; stage {item.reporter?.trust_stage ?? 0} &middot;{" "}
                      {new Date(item.report.created_at).toLocaleDateString("en-PH", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                  {item.report.notes ? (
                    <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                      {item.report.notes}
                    </p>
                  ) : null}
                  {safeHref(item.report.evidence_url) ? (
                    <a
                      href={safeHref(item.report.evidence_url) as string}
                      target="_blank"
                      rel="noopener noreferrer nofollow"
                      className="mt-1 inline-flex items-center gap-1 text-[12px] text-[var(--accent-primary)] hover:underline"
                    >
                      <LinkSimple size={13} />
                      Evidence
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>

            {target ? (
              <Link
                href={`/reviews/${target.id}`}
                className="mt-4 inline-flex h-9 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-4 text-[13px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)]"
              >
                Open the review
              </Link>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export default ReportQueue;
