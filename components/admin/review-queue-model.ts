/**
 * The Review Queue's presentation logic, kept out of the screen component.
 *
 * Same arrangement as `components/analytics/globe-model.ts`: the screen is a
 * client component the frontend test runner cannot render, so everything that
 * can be got wrong — which row is high priority, which number a cell shows,
 * which cells have no number to show — lives here as plain functions with
 * structural input types and no imports.
 *
 * The rule this module exists to enforce: a moderation console must never
 * print a number it cannot source. Every metric frame 5017:3758 draws is
 * either read from the queue card the API actually returned, or returned as an
 * unavailable `Stat` carrying the reason. There is no third case, and in
 * particular there is no "0" standing in for "we do not measure this" — on a
 * fraud-review screen those two read identically and mean opposite things.
 */

export type Priority = "High" | "Normal" | "Low";

/** A queue card, narrowed to the fields this module reads. */
export type QueueCard = {
  review: {
    id: string;
    review_id: string | null;
    title: string;
    verification_status: string;
    created_at: string;
    wilson_score: string;
    helpful_votes: number;
    unhelpful_votes: number;
  };
  product: { canonical_name: string | null };
  author: { display_name: string | null; reputation_score: string } | null;
  signals: {
    velocity: boolean;
    collusion: boolean;
    duplicate_content: boolean;
    author_account_age_days: number;
    author_review_count: number;
  };
};

/** A filed report, narrowed to the fields this module reads. */
export type ReportRow = {
  report: { target_ref: string | null };
  target: { id: string } | null;
  target_report_count: number;
};

/**
 * One cell of the detail panel: a value the API supplied, or the reason it
 * could not. Callers render the reason; they never invent a value.
 */
export type Stat =
  | { label: string; available: true; value: string }
  | { label: string; available: false; value: null; reason: string };

const available = (label: string, value: string): Stat => ({
  label,
  available: true,
  value,
});

const unavailable = (label: string, reason: string): Stat => ({
  label,
  available: false,
  value: null,
  reason,
});

/* -------------------------------------------------------------- priority */

/**
 * Priority is DERIVED from the advisory fraud signals the queue already
 * returns. The backend carries no priority or score column — confirmed against
 * `QueueSignals`, whose six fields are frozen by `test_telemetry_isolation.py`
 * — so inventing a ranking here would be inventing a moderation policy.
 *
 *   High    any signal fired — duplicate content, collusion, or velocity
 *   Normal  no signal, but the proof of purchase is unverified
 *   Low     verified, and nothing flagged
 */
export function priorityOf(item: QueueCard): Priority {
  const s = item.signals;
  if (s.duplicate_content || s.collusion || s.velocity) return "High";
  if (item.review.verification_status !== "verified") return "Normal";
  return "Low";
}

/* ------------------------------------------------------------------ time */

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "3s ago" / "5m ago" / "2h ago" / "4d ago" / "6mo ago" / "2y ago". */
export function relativeAge(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (seconds < MINUTE) return `${Math.floor(seconds)}s ago`;
  if (seconds < HOUR) return `${Math.floor(seconds / MINUTE)}m ago`;
  if (seconds < DAY) return `${Math.floor(seconds / HOUR)}h ago`;
  return accountAgeLabel(Math.floor(seconds / DAY));
}

/**
 * The same wording from a whole-day count, which is what
 * `signals.author_account_age_days` is — an integer, not a timestamp.
 */
export function accountAgeLabel(days: number): string {
  const whole = Math.max(0, Math.floor(days));
  if (whole < 30) return `${whole}d ago`;
  if (whole < 365) return `${Math.floor(whole / 30)}mo ago`;
  return `${Math.floor(whole / 365)}y ago`;
}

/* ------------------------------------------------------------ table rows */

export function queueRows<T extends QueueCard>(
  items: T[],
  options: { query: string; priority: Priority | ""; newestFirst: boolean },
): T[] {
  const needle = options.query.trim().toLowerCase();

  const matched = items.filter((item) => {
    if (options.priority && priorityOf(item) !== options.priority) return false;
    if (!needle) return true;
    return (
      item.review.title.toLowerCase().includes(needle) ||
      (item.product.canonical_name ?? "").toLowerCase().includes(needle) ||
      (item.author?.display_name ?? "").toLowerCase().includes(needle)
    );
  });

  // Sorted on the copy `filter` produced, never on the caller's array: the
  // screen passes React props straight in.
  matched.sort((a, b) => {
    const delta =
      new Date(b.review.created_at).getTime() - new Date(a.review.created_at).getTime();
    return options.newestFirst ? delta : -delta;
  });

  return matched;
}

export function paginate<T>(rows: T[], pageSize: number, page: number) {
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(Math.max(1, page), pageCount);
  const start = (current - 1) * pageSize;
  const visible = rows.slice(start, start + pageSize);

  return {
    visible,
    pageCount,
    current,
    /** 1-based inclusive range, or 0–0 when there is nothing to show. */
    firstIndex: visible.length === 0 ? 0 : start + 1,
    lastIndex: start + visible.length,
  };
}

/**
 * The ID column.
 *
 * The frame draws a short sequential "B-270". No such counter exists: the
 * backend's human reference is `review_id`, minted as `rev_<10 hex>`
 * (`review_service.py`). The real reference is what a moderator can paste into
 * a search or a report, so it wins over the frame's placeholder shape.
 */
export function reviewIdLabel(review: { review_id: string | null; id: string }): string {
  return review.review_id ?? review.id.slice(0, 8);
}

/**
 * How many reports were filed against this review, or `null` when this console
 * cannot tell.
 *
 * Reports are already fetched for the Report tab, so this costs no request.
 * `target_ref` holds either the UUID or the human reference depending on how
 * the report was filed — `admin_overview_service._reported_review_ids` unions
 * both forms for exactly this reason, and matching only one would under-count.
 * When a row matches, `target_report_count` is the backend's own total for
 * that target, so it is exact and is returned as-is.
 *
 * NULL, NEVER ZERO, when nothing matches. The feed this searches is the 50
 * most recent reports, and `getReports` returns an empty array when the fetch
 * FAILS as well as when there is genuinely nothing. So "no matching row" has
 * three possible causes — no reports exist, this review's reports fell outside
 * the newest 50, or the request errored — and only the first would justify
 * printing "0". Printing it anyway tells a moderator this review is unreported
 * when it may be the most-reported one on the site.
 */
export function reportCountFor(item: QueueCard, reports: ReportRow[]): number | null {
  const ids = new Set([item.review.id, item.review.review_id].filter(Boolean));
  for (const row of reports) {
    if (
      (row.report.target_ref && ids.has(row.report.target_ref)) ||
      (row.target && ids.has(row.target.id))
    ) {
      return row.target_report_count;
    }
  }
  return null;
}

/* ------------------------------------------------------------- engagement */

const NO_VIEW_SOURCE =
  "Views are counted per hour in review_view_buckets, but no admin or " +
  "review-facing endpoint reads that table — only the reviewer's own " +
  "dashboard does. Never sourced from reading telemetry.";

const NO_SHARE_SOURCE =
  "Nothing in this build counts shares: there is no share column, share " +
  "event table or share endpoint anywhere in the backend.";

const NO_COMMENT_SOURCE =
  "comment_count is served by GET /reviews/{id}/full, which the queue does " +
  "not call. The queue card carries no comment total.";

const NO_REPORT_EVIDENCE =
  "This console reads only the 50 most recent reports, and that partial feed " +
  "names no report against this review. A failed reports request looks " +
  "identical to an empty one, so absence here is not evidence of zero.";

const NO_TOP_COMMENT =
  "Comments are returned oldest-first with no ranking parameter, so there is " +
  "no server-side notion of a top comment to show.";

/**
 * The engagement panel.
 *
 * Upvotes, downvotes and the report count are real. Views, shares, comments
 * and the top comment have no source that reaches this screen, and say so.
 */
export function engagementFor(item: QueueCard, reports: ReportRow[]) {
  const reportCount = reportCountFor(item, reports);

  return {
    upvotes: item.review.helpful_votes,
    downvotes: item.review.unhelpful_votes,
    views: unavailable("Views", NO_VIEW_SOURCE),
    shares: unavailable("Shares", NO_SHARE_SOURCE),
    reports: reportCount === null
      ? unavailable("Reports", NO_REPORT_EVIDENCE)
      : available("Reports", String(reportCount)),
    comments: unavailable("Comments", NO_COMMENT_SOURCE),
    topComment: unavailable("Top comment", NO_TOP_COMMENT),
  };
}

/* ---------------------------------------------------------- author card */

const NO_VERIFIED_COUNT =
  "The queue card carries no verified-review count. signals.author_review_" +
  "count includes unverified work, so it cannot stand in for this.";

/**
 * The four stats the frame draws beside the author's name.
 *
 * Age, Trust Score and Total Reviews come off the queue card. Verified
 * Reviews does not exist on it — `users.verified_review_count` is real, but
 * `QueueAuthor` does not serialize it.
 */
export function authorTrustStats(item: QueueCard): Stat[] {
  // reputation_score is a Decimal serialized as a string. An empty or
  // malformed one must not become "NaN" on screen next to a reviewer's name.
  const score = item.author ? Number(item.author.reputation_score) : Number.NaN;

  return [
    available("Age", accountAgeLabel(item.signals.author_account_age_days)),
    Number.isFinite(score) && item.author?.reputation_score !== ""
      ? available("Trust Score", String(Math.round(score)))
      : unavailable(
          "Trust Score",
          item.author
            ? "This author's reputation score did not parse as a number."
            : "This review's author account no longer exists.",
        ),
    available("Total Reviews", String(item.signals.author_review_count)),
    unavailable("Verified Reviews", NO_VERIFIED_COUNT),
  ];
}

/* --------------------------------------------------- panels with no source */

/**
 * The per-review Voting Distribution globe and the flagged-voter cards.
 *
 * `review_first_vote_geo_buckets` does store per-review vote geography, but it
 * is write-only: no route reads it, and `test_telemetry_isolation.py` floods
 * that exact table while asserting the moderator queue card is unchanged. So
 * there is nothing to render and, until a reviewed read path exists, nothing
 * that may be rendered. Flagged-voter counts have no source at all.
 */
export const VOTING_GEOGRAPHY_UNAVAILABLE =
  "Per-review vote geography is stored in review_first_vote_geo_buckets but " +
  "no endpoint serves it, and the telemetry-isolation gate requires the " +
  "moderator queue to stay independent of it. Nothing here is derived from " +
  "reading telemetry.";

export const FLAGGED_VOTERS_UNAVAILABLE =
  "No flagged-voter aggregate exists in this build: votes carry no geography, " +
  "no trust bucketing and no fraud classification.";

export const REVERSE_IMAGE_SEARCH_UNAVAILABLE =
  "FR-8 layer 3 names no provider. Nothing in this build performs reverse " +
  "image search or plagiarism scoring.";

/* ------------------------------------------------- selection and tab links */

/** The console's four tabs, in the order frame 5017:3758 draws them. */
export type Tab = "reviews" | "answers" | "report" | "support";

const TAB_KEYS: Tab[] = ["reviews", "answers", "report", "support"];

export const QUEUE_ROUTE = "/moderate/review-queue";

export function isTab(value: string | null | undefined): value is Tab {
  return typeof value === "string" && (TAB_KEYS as string[]).includes(value);
}

/**
 * The row the detail panel shows.
 *
 * Chosen from the rows CURRENTLY VISIBLE, never from the whole queue. Picking
 * from the full source let the panel keep describing a review that the active
 * filter or the current page had scrolled away — a moderator reading the
 * evidence for one review while the table highlighted none of it, which is
 * exactly how the wrong review gets actioned.
 */
export function selectVisibleQueueItem<T extends QueueCard>(
  visible: T[],
  selectedId: string | null,
): T | null {
  if (visible.length === 0) return null;
  return visible.find((row) => row.review.id === selectedId) ?? visible[0];
}

/**
 * Where a tab points.
 *
 * The tabs are links, not local state. `AdminShell` titles the page from
 * `?tab` and `AdminNav` highlights its Q&A entry by matching `tab=answers`, so
 * a tab held only in component state left the heading and the rail describing
 * a different tab than the one on screen — and made the view unshareable.
 * The URL is the single source of truth; these hrefs are how it changes.
 *
 * The active priority filter rides along so switching tabs and coming back
 * does not silently widen what the moderator is looking at.
 */
export function tabHref(tab: Tab, priority: Priority | ""): string {
  const params = new URLSearchParams({ tab });
  if (priority) params.set("priority", priority.toLowerCase());
  return `${QUEUE_ROUTE}?${params.toString()}`;
}

/**
 * The short label on the Voting Distribution panel.
 *
 * Wording matters here. `review_first_vote_geo_buckets` DOES record per-review
 * vote geography — `request_traffic_service.record_first_vote_geo` writes a row
 * on every newly created vote. What does not exist is a read path. Saying the
 * data is "not measured" states the opposite of the truth about what this
 * product collects, which is the wrong answer to give anyone asking a privacy
 * or retention question.
 */
export const VOTING_GEOGRAPHY_SHORT =
  "Collected per review, but not served to this console.";
