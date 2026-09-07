"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowFatDown,
  ArrowFatUp,
  ArrowsDownUp,
  CaretDown,
  CaretLeft,
  CaretRight,
  ChatCircle,
  Eye,
  Flag,
  GlobeHemisphereEast,
  ImageBroken,
  MagnifyingGlass,
  ShareNetwork,
  Sliders,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";

import { QaAnswersTab } from "@/components/admin/QaAnswersTab";
import type { QaQuestion } from "@/components/admin/qa-answers-model";
import {
  FLAGGED_VOTERS_UNAVAILABLE,
  REVERSE_IMAGE_SEARCH_UNAVAILABLE,
  VOTING_GEOGRAPHY_UNAVAILABLE,
  accountAgeLabel,
  authorTrustStats,
  engagementFor,
  paginate,
  priorityOf,
  queueRows,
  relativeAge,
  reviewIdLabel,
  type Priority,
  type Stat,
} from "@/components/admin/review-queue-model";
import { TrustBadge } from "@/components/ui/TrustBadge";
import type { QueueItem, ReportItem } from "@/lib/moderation";

/**
 * The Review Queue, built to frame 5017:3758.
 *
 * That frame is its own screen — a table on the left, a stacked detail column
 * on the right, tabs across the top and pagination at the foot.
 *
 * Everything derived rather than served is derived in
 * `review-queue-model.ts`, which the frontend test suite covers directly:
 * Priority from the advisory fraud signals, Score from the review's real
 * `wilson_score`, the ID from the backend's own `review_id`.
 *
 * WHERE THE FRAME DRAWS A NUMBER THIS BUILD CANNOT SOURCE, the panel says so
 * in place rather than showing a plausible one. That is not a shortcut around
 * the design: each case below was checked against the backend first, and each
 * is a genuine absence, not unfinished UI.
 *
 *   Views / Shares / Comments / top comment   no admin read path exists
 *   Voting Distribution globe + city bars     write-only geo table, no route
 *   Flagged voters, per-voter risk table      no data and no methodology
 *   Reverse image search / plagiarism         no provider in this build
 *   Verified Reviews (author card)            not on QueueAuthor
 *
 * A "0" in any of those cells would read as a measurement. On a fraud-review
 * screen that is the one mistake worth designing against.
 */

type Tab = "reviews" | "answers" | "report" | "support";

const TABS: { key: Tab; label: string }[] = [
  { key: "reviews", label: "Reviews" },
  { key: "answers", label: "Answers" },
  { key: "report", label: "Report" },
  { key: "support", label: "Support" },
];

/**
 * The frame's pill colours, mapped onto the vendored tokens.
 *
 * Low is drawn `#f17a23` on `#fcf8e7` — orange type on cream, not the yellow
 * the earlier build used, which put yellow text on a yellow ground.
 */
const PRIORITY_TONE: Record<Priority, string> = {
  High: "bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] text-[var(--accent-danger)]",
  Normal: "bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] text-[var(--accent-trust)]",
  Low: "bg-[color-mix(in_srgb,var(--accent-star)_14%,transparent)] text-[var(--accent-primary)]",
};

const PAGE_SIZES = [10, 25, 50];

/** The table's two lists. The frame labels these "In review" and "Archive". */
type QueueList = "in_review" | "edited";

export function ReviewQueueScreen({
  pending,
  edited,
  reports,
  questions,
  initialTab,
  initialPriority,
  now,
}: {
  pending: QueueItem[];
  edited: QueueItem[];
  reports: ReportItem[];
  questions: QaQuestion[];
  initialTab: Tab;
  initialPriority: Priority | null;
  /**
   * The instant the server rendered this page, used for every "3s ago".
   *
   * Not `Date.now()` read inside the component: this is a Client Component, so
   * React renders it on the server too, and a clock read at each render makes
   * the server's HTML and the client's first render disagree on any row posted
   * seconds ago — "Hydration failed … this tree will be regenerated", which
   * `console-health.spec.ts` fails on and which throws away the server's work
   * for the whole table. Passing the timestamp down makes both renders agree.
   */
  now: number;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [list, setList] = useState<QueueList>("in_review");
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState<Priority | "">(initialPriority ?? "");
  const [sortNewest, setSortNewest] = useState(true);
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(
    pending[0]?.review.id ?? null,
  );

  const source = list === "in_review" ? pending : edited;

  const rows = useMemo(
    () => queueRows(source, { query, priority, newestFirst: sortNewest }),
    [source, query, priority, sortNewest],
  );

  const { visible, pageCount, current, firstIndex, lastIndex } = paginate(rows, pageSize, page);
  const selected = source.find((i) => i.review.id === selectedId) ?? visible[0] ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Tabs — the frame draws Reviews / Answers / Report / Support as pills
          sitting on the workspace card's top edge. */}
      <div className="flex shrink-0 flex-wrap items-center gap-2 pb-3">
        {TABS.map((t) => {
          const count =
            t.key === "reviews" ? pending.length
            : t.key === "report" ? reports.length
            : t.key === "answers" ? questions.length
            : 0;

          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              aria-current={tab === t.key ? "page" : undefined}
              className={`rounded-[var(--radius-sm)] px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                tab === t.key
                  ? "bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] text-[var(--accent-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
              }`}
            >
              {t.label}
              {count > 0 ? <span className="ml-1.5 text-[11px] opacity-70">{count}</span> : null}
            </button>
          );
        })}
      </div>

      {tab === "reviews" ? (
        <>
          {/* Toolbar — the frame puts the list switch on the left and the
              filter / sort / search controls on the right. */}
          <div className="flex shrink-0 flex-wrap items-center gap-3 pb-3">
            <div className="inline-flex rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-0.5 shadow-[var(--shadow-card)]">
              {/* The frame's second segment reads "Archive". Nothing archives a
                  review in this build and no endpoint serves one, so the
                  segment carries the second list the queue API actually
                  returns: reviews edited after their affiliate link was
                  attached, which until now had no screen of their own. */}
              {([
                ["in_review", "In review", pending.length],
                ["edited", "Edited", edited.length],
              ] as const).map(([key, label, count]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setList(key);
                    setPage(1);
                  }}
                  aria-pressed={list === key}
                  className={`rounded-[var(--radius-sm)] px-3 py-1.5 text-[13px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                    list === key
                      ? "text-[var(--accent-primary)]"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {label}
                  {count > 0 ? <span className="ml-1.5 text-[11px] opacity-70">{count}</span> : null}
                </button>
              ))}
            </div>

            <label className="ml-auto inline-flex items-center gap-1.5 text-[13px] text-[var(--text-secondary)]">
              <Sliders size={16} />
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
              <ArrowsDownUp size={16} />
              {sortNewest ? "Newest first" : "Oldest first"}
            </button>

            <div className="relative w-full max-w-[18rem]">
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

          {/* Table + detail. Each scrolls in its own pane; the shell does not.
              The approved frame is 1280 wide and that is where the split earns
              its place; below it the table pane fell under the table's own
              minimum and clipped the Date column, so the panel stacks
              underneath instead and the table gets the full width. */}
          {/* The frame splits its 1280 canvas almost evenly — a ~560px table
              region and a ~600px detail column — so the detail panel has room
              for the review beside its evidence. An earlier 2.2:1 split
              starved that column and wrapped the evidence one word per line. */}
          <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
            <section
              aria-labelledby="queue-table-heading"
              className="flex min-h-0 flex-col overflow-hidden rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]"
            >
              <h2 id="queue-table-heading" className="sr-only">
                {list === "in_review"
                  ? "Reviews awaiting moderation"
                  : "Reviews edited since their affiliate link was attached"}
              </h2>

              <div className="min-h-0 flex-1 overflow-auto">
                {/* table-fixed with explicit column shares, so the Date column
                    is never squeezed off the end by a long review title.
                    Below 32rem it scrolls horizontally in its own pane, which
                    is the right behaviour on a phone. */}
                <table className="w-full min-w-[34rem] table-fixed border-collapse text-left">
                  {/* ID gets the room the backend's real reference needs:
                      `review_id` is `rev_` + 10 hex, not the frame's short
                      "B-270", and a moderator pastes it into a search. */}
                  <colgroup>
                    <col style={{ width: "20%" }} />
                    <col style={{ width: "25%" }} />
                    <col style={{ width: "21%" }} />
                    <col style={{ width: "9%" }} />
                    <col style={{ width: "13%" }} />
                    <col style={{ width: "12%" }} />
                  </colgroup>
                  <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
                    {/* Header and cell padding match column for column — they
                        did not before, so every heading sat 4px off its data. */}
                    <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
                      <th className="px-4 py-3 font-medium">ID</th>
                      <th className="px-4 py-3 font-medium">Title</th>
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
                          {source.length === 0
                            ? list === "in_review"
                              ? "Nothing is awaiting moderation."
                              : "No review has been edited since its link was attached."
                            : "No queued review matches this filter."}
                        </td>
                      </tr>
                    ) : (
                      visible.map((item) => {
                        const p = priorityOf(item);
                        const isSel = item.review.id === selected?.review.id;
                        const author = item.author?.display_name ?? "Unknown";
                        return (
                          <tr
                            key={item.review.id}
                            onClick={() => setSelectedId(item.review.id)}
                            className={`cursor-pointer border-t border-[var(--border-subtle)] text-[12px] transition-colors hover:bg-[var(--line-hairline-10)] ${
                              isSel ? "bg-[var(--line-hairline-10)]" : ""
                            }`}
                          >
                            <td
                              className="truncate px-4 py-3 font-mono text-[11px] text-[var(--text-secondary)]"
                              title={reviewIdLabel(item.review)}
                            >
                              {reviewIdLabel(item.review)}
                            </td>
                            <td className="truncate px-4 py-3 text-[var(--text-primary)]" title={item.review.title}>
                              {item.review.title}
                            </td>
                            <td className="px-4 py-3 text-[var(--text-primary)]">
                              {/* The frame draws a 24px avatar beside the name.
                                  QueueAuthor carries no avatar_url, so the
                                  initial stands in rather than a stock face. */}
                              <span className="flex min-w-0 items-center gap-2">
                                <span
                                  aria-hidden="true"
                                  className="grid size-6 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[10px] font-bold text-[var(--text-on-brand)]"
                                >
                                  {author.slice(0, 1).toUpperCase()}
                                </span>
                                <span className="truncate">{author}</span>
                              </span>
                            </td>
                            <td className="px-4 py-3 [font-variant-numeric:tabular-nums] text-[var(--text-primary)]">
                              {Number(item.review.wilson_score).toFixed(2)}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`inline-block rounded-[var(--radius-pill)] px-3 py-1 text-[12px] ${PRIORITY_TONE[p]}`}
                              >
                                {p}
                              </span>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-[var(--text-muted)]">
                              {relativeAge(item.review.created_at, now)}
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
                    onClick={() => setPage(Math.max(1, current - 1))}
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
                    onClick={() => setPage(Math.min(pageCount, current + 1))}
                    disabled={current === pageCount}
                    aria-label="Next page"
                    className="grid h-7 w-7 place-items-center rounded-[var(--radius-sm)] text-[var(--text-secondary)] disabled:opacity-35 enabled:hover:bg-[var(--line-hairline-10)]"
                  >
                    <CaretRight size={14} weight="bold" />
                  </button>
                </nav>

                <p className="text-[12px] text-[var(--text-secondary)]">
                  Showing {firstIndex}&ndash;{lastIndex} of {rows.length}
                  {rows.length !== source.length ? ` (filtered from ${source.length})` : ""}
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

            <ReviewDetail item={selected} edited={edited} reports={reports} />
          </div>
        </>
      ) : null}

      {tab === "answers" ? <QaAnswersTab questions={questions} now={now} /> : null}

      {tab === "report" ? <ReportsTab reports={reports} now={now} /> : null}

      {tab === "support" ? <SupportTab /> : null}
    </div>
  );
}

/**
 * The Support tab.
 *
 * Inert on purpose, and the one place in this screen where "Soon" is the whole
 * answer: there is no support-ticket entity, table or `/admin/support` route
 * anywhere in the build, so there is nothing to render and nothing to stub
 * against. It keeps its position because the frame draws it, and it mirrors
 * `AdminNav`'s existing blocked-item pattern — short status, full reason.
 */
function SupportTab() {
  return (
    <div className="mt-2 max-w-[46rem] rounded-[var(--radius-md)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
      <p className="flex items-center gap-2">
        <span className="text-[15px] font-semibold text-[var(--text-primary)]">Support</span>
        <span className="rounded-[var(--radius-pill)] bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--accent-primary)]">
          Soon
        </span>
      </p>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
        There is no support-ticket system in this build — no ticket table, no{" "}
        <code className="rounded bg-[var(--surface-app)] px-1 py-0.5 text-[12px]">/admin/support</code>{" "}
        route, and nothing that files or routes a request for help. The tab is
        drawn in the approved frame, so it keeps its place and says plainly that
        nothing sits behind it rather than opening an empty screen.
      </p>
      <p className="mt-3 text-[13px] text-[var(--text-secondary)]">
        Reported content is handled on the{" "}
        <span className="font-medium text-[var(--text-primary)]">Report</span> tab.
      </p>
    </div>
  );
}

function ReportsTab({ reports, now }: { reports: ReportItem[]; now: number }) {
  return (
    <div className="mt-2 min-h-0 flex-1 overflow-y-auto">
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
                  {relativeAge(r.report.created_at, now)}
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

/** The frame's right-hand column: who wrote it, what it says, and the evidence. */
function ReviewDetail({
  item,
  edited,
  reports,
}: {
  item: QueueItem | null;
  edited: QueueItem[];
  reports: ReportItem[];
}) {
  if (!item) {
    return (
      <aside className="hidden min-h-0 overflow-y-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)] xl:block">
        <p className="text-[13px] text-[var(--text-secondary)]">
          Select a row to inspect the review, its author and its evidence.
        </p>
      </aside>
    );
  }

  const s = item.signals;
  const wasEdited = edited.some((e) => e.review.id === item.review.id);
  const stats = authorTrustStats(item);
  const engagement = engagementFor(item, reports);
  const author = item.author?.display_name ?? "Unknown author";

  return (
    <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]">
      {/* 1. Author trust card (6606:971). */}
      <Panel>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="grid size-8 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[12px] font-bold text-[var(--text-on-brand)]"
            >
              {author.slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[12px] text-[var(--text-primary)]">{author}</span>
              <span className="block text-[10px] font-light text-[var(--text-secondary)]">
                Trust stage {item.author?.trust_stage ?? 0}
              </span>
            </span>
          </div>

          <dl className="grid flex-1 grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
            {stats.map((stat) => (
              <StatCell
                key={stat.label}
                stat={stat}
                render={
                  stat.label === "Trust Score" && item.author ? (
                    <TrustBadge
                      levelName={null}
                      stage={item.author.trust_stage}
                      score={item.author.reputation_score}
                      compact
                      plain
                    />
                  ) : null
                }
              />
            ))}
          </dl>
        </div>
      </Panel>

      {/* 2. The review itself (6606:970) beside the evidence column. */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel>
          <p className="text-[10px] font-bold text-[var(--text-primary)]">
            {item.product.canonical_name ?? "Unlisted product"}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-primary)]">
            {item.review.discussion}
          </p>

          {/* The frame draws a three-photo grid. `reviews.photo_url` is a
              single column and the upload endpoint returns one URL, so one
              photo is the whole set, not the first of three. */}
          {item.review.photo_url ? (
            <div className="relative mt-3 aspect-[3/2] w-full overflow-hidden rounded-[var(--radius-sm)] bg-[var(--line-hairline-10)]">
              <Image
                src={item.review.photo_url}
                alt=""
                fill
                sizes="(max-width: 1280px) 100vw, 320px"
                className="object-cover"
              />
            </div>
          ) : (
            <p className="mt-3 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-3 py-2 text-[11px] text-[var(--text-secondary)]">
              No photo was attached to this review.
            </p>
          )}

          <Link
            href={`/reviews/${item.review.id}`}
            className="mt-2 inline-block text-[12px] underline hover:text-[var(--accent-primary)]"
          >
            Open the full review
          </Link>
        </Panel>

        <Panel>
          <p className="text-[10px] font-light text-[var(--text-secondary)]">Receipt</p>
          {/* The receipt object itself is deliberately NOT loaded here.
              `GET /reviews/{id}/receipt` mints a 300-second signed URL and
              writes a `receipt_view` moderation-log row for every moderator
              fetch, so auto-loading it as rows are clicked through would file
              an audit entry for a receipt nobody looked at. */}
          <p className="mt-1 text-[12px] text-[var(--text-primary)]">
            {item.review.has_receipt ? "Attached" : "None submitted"}
          </p>
          {item.review.has_receipt ? (
            <p className="mt-1 text-[10px] leading-snug text-[var(--text-muted)]">
              Opened from the review itself, so the access is logged against a
              deliberate look rather than a click-through.
            </p>
          ) : null}

          <p className="mt-4 text-[10px] font-light text-[var(--text-secondary)]">
            Reverse Image Search
          </p>
          {/* The frame draws a square result tile beside two small stat tiles.
              The tile keeps its shape; the long reason lives in the tooltip so
              a 200px column is not filled with a paragraph. */}
          <div className="mt-1 flex items-stretch gap-2">
            <div
              title={REVERSE_IMAGE_SEARCH_UNAVAILABLE}
              className="grid flex-1 place-items-center gap-1 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-2 py-3 text-center"
            >
              <ImageBroken size={24} className="text-[var(--text-muted)]" aria-hidden="true" />
              <span className="text-[10px] leading-tight text-[var(--text-secondary)]">
                No provider
              </span>
            </div>

            <div className="flex flex-1 flex-col justify-center rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-3 py-2">
              <span className="text-[10px] font-light text-[var(--text-secondary)]">
                Wilson Score
              </span>
              <span className="text-[12px] text-[var(--accent-success)] [font-variant-numeric:tabular-nums]">
                {Number(item.review.wilson_score).toFixed(2)}
              </span>
            </div>
          </div>
          <p className="mt-1 text-[10px] leading-snug text-[var(--text-muted)]">
            Plagiarism scoring is not procured in this build.
          </p>
        </Panel>
      </div>

      {/* 3. Engagement (6606:995). */}
      <Panel>
        <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
          <dl className="min-w-[7rem]">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] text-[var(--text-primary)]">Upvote</dt>
              <dd className="inline-flex items-center gap-1 text-[10px] text-[var(--text-primary)]">
                {engagement.upvotes}
                <ArrowFatUp size={16} weight="fill" className="text-[var(--accent-success)]" />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] text-[var(--text-primary)]">Downvote</dt>
              <dd className="inline-flex items-center gap-1 text-[10px] text-[var(--text-primary)]">
                {engagement.downvotes}
                <ArrowFatDown size={16} weight="fill" className="text-[var(--accent-danger)]" />
              </dd>
            </div>
          </dl>

          <div className="flex flex-wrap items-start gap-x-5 gap-y-3">
            <Metric stat={engagement.views} icon={<Eye size={16} />} />
            <Metric stat={engagement.shares} icon={<ShareNetwork size={16} />} />
            <Metric
              stat={engagement.reports}
              icon={<Flag size={16} className="text-[var(--accent-danger)]" />}
              hint="Counted from the 50 most recent reports this console loaded."
            />
            <Metric stat={engagement.comments} icon={<ChatCircle size={16} />} />
          </div>
        </div>

        <p
          title={engagement.topComment.available ? undefined : engagement.topComment.reason}
          className="mt-3 border-t border-[var(--border-subtle)] pt-2 text-[10px] leading-snug text-[var(--text-muted)]"
        >
          No top comment: comments have no server-side ranking.
        </p>
      </Panel>

      {/* 4 + 5. Voting Distribution and the flagged-voter cards.
          Both are drawn in the frame and neither has a source; see the
          constants in review-queue-model.ts for exactly why. The per-voter
          risk table the frame draws below them is deliberately absent: no
          fraud-risk methodology is defined anywhere in this codebase, so
          there is nothing to render that would not be invented. */}
      <Panel>
        <p className="text-[12px] font-semibold text-[var(--text-primary)]">
          Voting Distribution
        </p>
        <div
          title={VOTING_GEOGRAPHY_UNAVAILABLE}
          className="mt-2 flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-3 py-2.5"
        >
          <GlobeHemisphereEast
            size={20}
            className="shrink-0 text-[var(--text-muted)]"
            aria-hidden="true"
          />
          <p className="text-[10px] leading-snug text-[var(--text-secondary)]">
            Not measured per review.{" "}
            <Link
              href="/moderate/analytics"
              className="underline hover:text-[var(--accent-primary)]"
            >
              Site-wide geography
            </Link>
          </p>
        </div>

        <div
          title={FLAGGED_VOTERS_UNAVAILABLE}
          className="mt-2 flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--surface-app)] px-3 py-2.5"
        >
          <UsersThree size={20} className="shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
          <p className="text-[10px] leading-snug text-[var(--text-secondary)]">
            No flagged-voter or per-voter risk data exists.
          </p>
        </div>
      </Panel>

      {/* The advisory signals, which are real and are the thing that actually
          drives the Priority column. */}
      <Panel>
        <p className="text-[12px] font-semibold text-[var(--text-primary)]">Signals</p>
        <ul className="mt-2 flex flex-col gap-1.5">
          <Signal
            fired={s.velocity}
            name="velocity"
            text="Posting velocity is unusual for this account."
          />
          <Signal
            fired={s.collusion}
            name="collusion"
            text="Voting pattern suggests collusion."
          />
          <Signal
            fired={s.duplicate_content}
            name="duplicate content"
            text="Body matches content already published elsewhere."
          />
          <Signal
            fired={wasEdited}
            name="post-link edit"
            text="Edited after its affiliate link was attached — re-check."
          />
        </ul>
        <p className="mt-2 text-[10px] text-[var(--text-muted)]">
          Account age {accountAgeLabel(s.author_account_age_days)}. Signals are
          advisory and never block automatically.
        </p>
      </Panel>
    </aside>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--text-primary)_2%,transparent)] p-4">
      {children}
    </section>
  );
}

/** One label/value pair, or the reason there is no value. */
function StatCell({ stat, render }: { stat: Stat; render?: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-light text-[var(--text-secondary)]">{stat.label}</dt>
      <dd className="text-[12px] text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {stat.available ? (
          (render ?? stat.value)
        ) : (
          <span title={stat.reason} className="text-[var(--text-muted)]">
            Not available
          </span>
        )}
      </dd>
    </div>
  );
}

/** One engagement figure, drawn as value-over-label like the frame. */
function Metric({
  stat,
  icon,
  hint,
}: {
  stat: Stat;
  icon: React.ReactNode;
  hint?: string;
}) {
  return (
    <div title={stat.available ? hint : stat.reason}>
      <p className="flex items-center gap-1 text-[12px] text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
        {stat.available ? stat.value : <span className="text-[var(--text-muted)]">—</span>}
        <span className="text-[var(--text-secondary)]" aria-hidden="true">
          {icon}
        </span>
      </p>
      <p className="text-[10px] font-light text-[var(--text-secondary)]">
        {stat.label}
        {stat.available ? null : <span className="sr-only"> — not available</span>}
      </p>
    </div>
  );
}

/**
 * One advisory signal, shown whether or not it fired.
 *
 * The clear ones are worth drawing: "no collusion signal" is a fact a
 * moderator acted on, and a list that only ever shows problems cannot be told
 * apart from a list that failed to load.
 */
function Signal({
  fired,
  name,
  text,
}: {
  fired: boolean;
  name: string;
  text: string;
}) {
  return (
    <li
      className={`rounded-[var(--radius-sm)] px-3 py-1.5 text-[11px] ${
        fired
          ? "bg-[color-mix(in_srgb,var(--accent-star)_14%,transparent)] text-[var(--text-primary)]"
          : "text-[var(--text-muted)]"
      }`}
    >
      {fired ? text : `No ${name} signal.`}
    </li>
  );
}
