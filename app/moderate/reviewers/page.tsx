import type { Metadata } from "next";
import Link from "next/link";

import { getReviewers } from "@/lib/moderation";

export const metadata: Metadata = { title: "Reviewers — bluntly admin" };

export default async function ReviewersPage() {
  const people = await getReviewers(100);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 pb-3">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Reviewers</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          {people
            ? `${people.total} account${people.total === 1 ? "" : "s"}, most published first.`
            : "Unable to load contributors right now."}{" "}
          Standing and output only &mdash; no email address and no session data reaches
          this screen.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        <table className="w-full min-w-[38rem] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Reviewer</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Trust stage</th>
              <th className="px-4 py-3 font-medium">Reputation</th>
              <th className="px-4 py-3 font-medium">Published</th>
              <th className="px-4 py-3 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody>
            {!people || people.rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                  {people ? "No accounts yet." : "Unable to load contributors."}
                </td>
              </tr>
            ) : (
              people.rows.map((p) => (
                <tr key={p.id} className="border-t border-[var(--border-subtle)] text-[13px]">
                  <td className="px-4 py-2.5">
                    {p.username ? (
                      <Link
                        href={`/u/${p.username}`}
                        className="font-medium text-[var(--text-primary)] underline hover:text-[var(--accent-primary)]"
                      >
                        {p.display_name ?? p.username}
                      </Link>
                    ) : (
                      <span className="text-[var(--text-secondary)]">
                        {p.display_name ?? "Unnamed"}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 capitalize text-[var(--text-secondary)]">{p.role}</td>
                  <td className="px-4 py-2.5 [font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                    {p.trust_stage}
                  </td>
                  <td className="px-4 py-2.5 [font-variant-numeric:tabular-nums] text-[var(--text-secondary)]">
                    {Number(p.reputation_score).toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 [font-variant-numeric:tabular-nums] font-medium text-[var(--text-primary)]">
                    {p.published_reviews}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-[12px] text-[var(--text-muted)]">
                    {new Date(p.joined).toLocaleDateString("en-PH", { dateStyle: "medium" })}
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
