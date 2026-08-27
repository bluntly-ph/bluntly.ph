"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CaretDown,
  CaretLeft,
  CaretRight,
  FunnelSimple,
  MagnifyingGlass,
  SortAscending,
  ThumbsDown,
  ThumbsUp,
} from "@phosphor-icons/react/dist/ssr";

import type { QueueItem, ReportItem } from "@/lib/moderation";

/**
 * The Review Queue, built to frame 5017:3758.
 *
 * That frame is its own 1280x832 screen — a table on the left, a detail panel
 * on the right, tabs across the top and pagination at the foot. It is not a
 * section of the Overview, which is how it had been built: a moderator had to
 * scroll past the whole dashboard to reach the work.
 *
 * Priority is DERIVED, never decorative. It reads the advisory fraud signals
 * the queue already returns:
 *
 *   High    any signal fired — duplicate content, collusion, or velocity
 *   Normal  no signal, but the proof of purchase is unverified
 *   Low     verified, and nothing flagged
 *
 * Score is the review's real `wilson_score`. Nothing here is invented: where a
 * metric the frame draws has no source yet, the cell says so instead of
 * showing a plausible number.
 */

type Tab = "reviews" | "answers" | "report" | "support";

const TABS: { key: Tab; label: string }[] = [
  { key: "reviews", label: "Reviews" },
  { key: "answers", label: "Answers" },
  { key: "report", label: "Report" },
  { key: "support", label: "Support" },
];

type Priority = "High" | "Normal" | "Low";

const PRIORITY_TONE: Record<Priority, string> = {
  High: "bg-[var(--accent-danger)]/12 text-[var(--accent-danger)]",
  Normal: "bg-[var(--accent-trust)]/12 text-[var(--accent-trust)]",
  Low: "bg-[var(--accent-star)]/15 text-[var(--accent-star)]",
};

function priorityOf(item: QueueItem): Priority {
  const s = item.signals;
  if (s.duplicate_content || s.collusion || s.velocity) return "High";
  if (item.review.verification_status !== "verified") return "Normal";
  return "Low";
}

function ago(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${Math.floor(secs)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  const days = Math.floor(secs / 86400);
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

const PAGE_SIZES = [10, 25, 50];

export function ReviewQueueScreen({
  pending,
  edited,
  reports,
  initialTab,
  initialPriority,
}: {
  pending: QueueItem[];
  edited: QueueItem[];
  reports: ReportItem[];
  initialTab: Tab;
  initialPriority: Priority | null;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState<Priority | "">(initialPriority ?? "");
  const [sortNewest, setSortNewest] = useState(true);
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(
    pending[0]?.review.id ?? null,
  );

  const rows = useMemo(() => {
    let list = [...pending];
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (i) =>
          i.review.title.toLowerCase().includes(q) ||
          (i.product.canonical_name ?? "").toLowerCase().includes(q) ||
          (i.author?.display_name ?? "").toLowerCase().includes(q),
      );
    }
    if (priority) list = list.filter((i) => priorityOf(i) === priority);
    list.sort((a, b) => {
      const t = new Date(b.review.created_at).getTime() - new Date(a.review.created_at).getTime();
      return sortNewest ? t : -t;
    });
    return list;
  }, [pending, query, priority, sortNewest]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(page, pageCount);
  const visible = rows.slice((current - 1) * pageSize, current * pageSize);
  const selected = pending.find((i) => i.review.id === selectedId) ?? visible[0] ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Tabs — the frame draws Reviews / Answers / Report / Support. */}
      <div className="flex shrink-0 flex-wrap items-center gap-5 border-b border-[var(--border-subtle)] px-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined}
            className={`border-b-2 pb-2.5 text-[13px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
              tab === t.key
                ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {t.label}
            {t.key === "reviews" && pending.length > 0 ? (
              <span className="ml-1.5 text-[11px] opacity-70">{pending.length}</span>
            ) : null}
            {t.key === "report" && reports.length > 0 ? (
              <span className="ml-1.5 text-[11px] opacity-70">{reports.length}</span>
            ) : null}
          </button>
        ))}
      </div>

      {tab === "reviews" ? (
        <>
          {/* Toolbar */}
          <div className="flex shrink-0 flex-wrap items-center gap-3 py-3">
            <label className="inline-flex items-center gap-1.5 text-[13px] text-[var(--text-secondary)]">
              <FunnelSimple size={16} />
              <span className="sr-only">Filter by priority</span>
              <select
                value={priority}
                onChange={(e) => {
                  setPriority(e.target.value as Priority | "");
                  setPage(1);
                }}
                className="rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--surface-card)] px-2 py-1 text-[13px] text-[var(--text-primary)]"
              >
                <option value="">All filters</option>
                <option value="High">High priority</option>
                <option value="Normal">Normal</option>
                <option value="Low">Low</option>
              </select>
            </label>

            <button
              type="button"
              onClick={() => setSortNewest((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-1 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
            >
              <SortAscending size={16} className={sortNewest ? "" : "rotate-180"} />
              {sortNewest ? "Newest first" : "Oldest first"}
            </button>

            <div className="relative ml-auto w-full max-w-[18rem]">
              <MagnifyingGlass
                size={16}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                type="search"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
                placeholder="Search title, product or author"
                aria-label="Search the queue"
                className="h-9 w-full rounded-[var(--radius-pill)] border border-[var(--border-subtle)] bg-[var(--surface-card)] pl-9 pr-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--accent-primary)]"
              />
            </div>
          </div>

          {/* Table + detail. Each scrolls in its own pane; the shell does not. */}
          <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
            <section
              aria-labelledby="queue-table-heading"
              className="flex min-h-0 flex-col overflow-hidden rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]"
            >
              <h2 id="queue-table-heading" className="sr-only">
                Reviews awaiting moderation
              </h2>

              <div className="min-h-0 flex-1 overflow-auto">
                <table className="w-full min-w-[36rem] border-collapse text-left">
                  <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
                    <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
                      <th className="px-3 py-3 font-medium">ID</th>
                      <th className="px-4 py-3 font-medium">Review</th>
                      <th className="px-4 py-3 font-medium">Author</th>
                      <th className="px-4 py-3 font-medium">Score</th>
                      <th className="px-4 py-3 font-medium">Priority</th>
                      <th className="px-4 py-3 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                          {pending.length === 0
                            ? "Nothing is awaiting moderation."
                            : "No queued review matches this filter."}
                        </td>
                      </tr>
                    ) : (
                      visible.map((item) => {
                        const p = priorityOf(item);
                        const isSel = item.review.id === selected?.review.id;
                        return (
                          <tr
                            key={item.review.id}
                            onClick={() => setSelectedId(item.review.id)}
                            className={`cursor-pointer border-t border-[var(--border-subtle)] text-[13px] transition-colors hover:bg-[var(--line-hairline-10)] ${
                              isSel ? "bg-[var(--line-hairline-10)]" : ""
                            }`}
                          >
                            <td className="px-4 py-3 font-mono text-[12px] text-[var(--text-secondary)]">
                              {item.review.review_id ?? item.review.id.slice(0, 8)}
                            </td>
                            <td className="max-w-[13rem] truncate px-3 py-3 text-[var(--text-primary)]">
                              {item.review.title}
                            </td>
                            <td className="px-4 py-3 text-[var(--text-secondary)]">
                              <span className="whitespace-nowrap">
                                {item.author?.display_name ?? "Unknown"}
                                <span className="mx-1.5 opacity-40">·</span>
                                <span className="text-[12px]">Lvl. {item.author?.trust_stage ?? 0}</span>
                              </span>
                            </td>
                            <td className="px-4 py-3 [font-variant-numeric:tabular-nums] text-[var(--text-primary)]">
                              {Number(item.review.wilson_score).toFixed(2)}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`inline-block rounded-[var(--radius-pill)] px-2.5 py-1 text-[11px] font-semibold ${PRIORITY_TONE[p]}`}
                              >
                                {p}
                              </span>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-[12px] text-[var(--text-muted)]">
                              {ago(item.review.created_at)}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination — the frame's footer row. */}
              <div className="flex shrink-0 flex-wrap items-center gap-3 border-t border-[var(--border-subtle)] px-4 py-3">
                <nav aria-label="Queue pages" className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setPage((n) => Math.max(1, n - 1))}
                    disabled={current === 1}
                    aria-label="Previous page"
                    className="grid h-7 w-7 place-items-center rounded-[var(--radius-sm)] text-[var(--text-secondary)] disabled:opacity-35 enabled:hover:bg-[var(--line-hairline-10)]"
                  >
                    <CaretLeft size={14} weight="bold" />
                  </button>
                  {Array.from({ length: pageCount }, (_, i) => i + 1)
                    .filter((n) => n === 1 || n === pageCount || Math.abs(n - current) <= 1)
                    .map((n, idx, arr) => (
                      <span key={n} className="flex items-center">
                        {idx > 0 && n - arr[idx - 1] > 1 ? (
                          <span className="px-1 text-[12px] text-[var(--text-muted)]">…</span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setPage(n)}
                          aria-current={n === current ? "page" : undefined}
                          className={`grid h-7 min-w-7 place-items-center rounded-[var(--radius-sm)] px-2 text-[12px] ${
                            n === current
                              ? "bg-[var(--accent-primary)] text-[var(--text-on-brand)]"
                              : "text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
                          }`}
                        >
                          {n}
                        </button>
                      </span>
                    ))}
                  <button
                    type="button"
                    onClick={() => setPage((n) => Math.min(pageCount, n + 1))}
                    disabled={current === pageCount}
                    aria-label="Next page"
                    className="grid h-7 w-7 place-items-center rounded-[var(--radius-sm)] text-[var(--text-secondary)] disabled:opacity-35 enabled:hover:bg-[var(--line-hairline-10)]"
                  >
                    <CaretRight size={14} weight="bold" />
                  </button>
                </nav>

                <p className="text-[12px] text-[var(--text-secondary)]">
                  Showing {visible.length === 0 ? 0 : (current - 1) * pageSize + 1}
                  &ndash;{(current - 1) * pageSize + visible.length} of {rows.length}
                  {rows.length !== pending.length ? ` (filtered from ${pending.length})` : ""}
                </p>

                <label className="ml-auto inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)]">
                  Show
                  <span className="relative">
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setPage(1);
                      }}
                      className="appearance-none rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--surface-card)] py-1 pl-2 pr-6 text-[12px] text-[var(--text-primary)]"
                    >
                      {PAGE_SIZES.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                    <CaretDown
                      size={11}
                      className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                    />
                  </span>
                </label>
              </div>
            </section>

            <ReviewDetail item={selected} edited={edited} />
          </div>
        </>
      ) : null}

      {tab === "answers" ? (
        <TabNotice
          title="Answers"
          body="Question and answer moderation is not wired into this console yet. Answers are moderated from the public Q&A surfaces, and there is no admin answer queue endpoint behind this tab."
          href="/questions"
          hrefLabel="Open public Q&A"
        />
      ) : null}

      {tab === "report" ? <ReportsTab reports={reports} /> : null}

      {tab === "support" ? (
        <TabNotice
          title="Support"
          body="No support-ticket system exists in this build. The tab is drawn in the approved frame, so it is kept in position and says plainly that there is nothing behind it rather than opening an empty screen."
        />
      ) : null}
    </div>
  );
}

function TabNotice({
  title,
  body,
  href,
  hrefLabel,
}: {
  title: string;
  body: string;
  href?: string;
  hrefLabel?: string;
}) {
  return (
    <div className="mt-6 max-w-[46rem] rounded-[var(--radius-md)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
      <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">{body}</p>
      {href ? (
        <Link
          href={href}
          className="mt-3 inline-block text-[13px] underline hover:text-[var(--accent-primary)]"
        >
          {hrefLabel}
        </Link>
      ) : null}
    </div>
  );
}

function ReportsTab({ reports }: { reports: ReportItem[] }) {
  return (
    <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
      {reports.length === 0 ? (
        <p className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-6 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-card)]">
          Nothing has been reported.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {reports.map((r) => (
            <li
              key={r.report.id}
              className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]"
            >
              <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                {r.report.reason ?? "Reported"}
                <span className="ml-2 text-[12px] font-normal text-[var(--text-muted)]">
                  {ago(r.report.created_at)}
                </span>
              </p>
              {r.report.notes ? (
                <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{r.report.notes}</p>
              ) : null}
              {r.report.target_ref ? (
                <Link
                  href={`/reviews/${r.report.target_ref}`}
                  className="mt-2 inline-block text-[12px] underline hover:text-[var(--accent-primary)]"
                >
                  Open the reported item
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The frame's right-hand panel: who wrote it, what it says, and the evidence. */
function ReviewDetail({ item, edited }: { item: QueueItem | null; edited: QueueItem[] }) {
  if (!item) {
    return (
      <aside className="hidden min-h-0 overflow-y-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)] lg:block">
        <p className="text-[13px] text-[var(--text-secondary)]">
          Select a row to inspect the review, its author and its evidence.
        </p>
      </aside>
    );
  }

  const s = item.signals;
  const wasEdited = edited.some((e) => e.review.id === item.review.id);

  return (
    <aside className="min-h-0 overflow-y-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[13px] font-bold text-[var(--text-on-brand)]">
          {(item.author?.display_name ?? "?").slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[14px] font-semibold text-[var(--text-primary)]">
            {item.author?.display_name ?? "Unknown author"}
          </span>
          <span className="block text-[12px] text-[var(--text-secondary)]">
            Trust stage {item.author?.trust_stage ?? 0}
          </span>
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-4">
        <Stat label="Account age" value={`${s.author_account_age_days}d`} />
        <Stat label="Trust score" value={String(item.author?.reputation_score ?? "0")} />
        <Stat label="Reviews" value={String(s.author_review_count)} />
        <Stat
          label="Verified"
          value={item.review.verification_status === "verified" ? "Yes" : "No"}
        />
      </dl>

      <h3 className="mt-5 text-[13px] font-semibold text-[var(--text-primary)]">
        {item.product.canonical_name ?? "Product"}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-secondary)]">
        {item.review.discussion.slice(0, 240)}
        {item.review.discussion.length > 240 ? "… " : " "}
        <Link
          href={`/reviews/${item.review.id}`}
          className="underline hover:text-[var(--accent-primary)]"
        >
          Full review
        </Link>
      </p>

      {item.review.photo_url ? (
        <div className="relative mt-3 h-40 w-full overflow-hidden rounded-[var(--radius-sm)] bg-[var(--line-hairline-10)]">
          <Image
            src={item.review.photo_url}
            alt=""
            fill
            sizes="(max-width: 1024px) 100vw, 380px"
            className="object-cover"
          />
        </div>
      ) : null}

      {/* The frame's evidence chips. Where a metric has no source in this
          build, the chip says so rather than showing a plausible number. */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Chip label="Receipt" value={item.review.has_receipt ? "Attached" : "None"} />
        <Chip label="Wilson score" value={Number(item.review.wilson_score).toFixed(2)} />
        <Chip
          label="Duplicate content"
          value={s.duplicate_content ? "Flagged" : "None"}
          tone={s.duplicate_content ? "warn" : undefined}
        />
        <Chip
          label="Reverse image"
          value="Not procured"
          hint="FR-8 layer 3 names no provider; nothing performs reverse image search in this build."
        />
      </div>

      <div className="mt-4 flex items-center gap-4 text-[13px]">
        <span className="inline-flex items-center gap-1.5 text-[var(--accent-success)]">
          <ThumbsUp size={15} weight="fill" /> {item.review.helpful_votes}
        </span>
        <span className="inline-flex items-center gap-1.5 text-[var(--accent-danger)]">
          <ThumbsDown size={15} weight="fill" /> {item.review.unhelpful_votes}
        </span>
      </div>

      {(s.velocity || s.collusion || wasEdited) ? (
        <ul className="mt-4 flex flex-col gap-1.5">
          {s.velocity ? <Signal text="Posting velocity is unusual for this account." /> : null}
          {s.collusion ? <Signal text="Voting pattern suggests collusion." /> : null}
          {wasEdited ? <Signal text="Edited after its affiliate link was attached — re-check." /> : null}
        </ul>
      ) : null}

      <p className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-[12px] text-[var(--text-muted)]">
        Signals are advisory and never block automatically.{" "}
        <Link href={`/reviews/${item.review.id}`} className="underline hover:text-[var(--accent-primary)]">
          Open the review to act on it
        </Link>
        .
      </p>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] text-[var(--text-muted)]">{label}</dt>
      <dd className="text-[13px] font-semibold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {value}
      </dd>
    </div>
  );
}

function Chip({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "warn";
  hint?: string;
}) {
  return (
    <div
      title={hint}
      className="rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-3 py-2"
    >
      <p className="text-[10px] uppercase tracking-[0.06em] text-[var(--text-muted)]">{label}</p>
      <p
        className={`text-[13px] font-semibold ${
          tone === "warn" ? "text-[var(--accent-danger)]" : "text-[var(--text-primary)]"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function Signal({ text }: { text: string }) {
  return (
    <li className="rounded-[var(--radius-sm)] bg-[var(--accent-star)]/12 px-3 py-1.5 text-[12px] text-[var(--text-primary)]">
      {text}
    </li>
  );
}
