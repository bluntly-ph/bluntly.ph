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
 * print a number it cannot source. Every metric the console draws is either
 * read from the queue card the API actually returned, or returned as an
 * unavailable `Stat` carrying the reason. There is no third case, and in
 * particular there is no "0" standing in for "we do not measure this" — on a
 * fraud-review screen those two read identically and mean opposite things.
 *
 * Priority obeys a second rule, added with the server-owned contract: this
 * module RENDERS the assessment and never computes one. Ordering, filtering
 * and banding are the policy's, decided over the whole backlog before the page
 * was cut. A helper here that re-sorted or re-filtered a page would be making
 * a whole-queue claim from the fifty rows it happens to hold.
 *
 * The design frames this screen was built to (5017:1738 / 5017:3758 / 6532:278)
 * were deleted from the Figma file on 2026-09-09 and replaced by a single
 * 1280x1943 "Admin Page - Review Queue" (6922:837). The layout below is still
 * the old frame's; the re-layout is its own piece of work.
 */

export type Priority = "High" | "Normal" | "Low";

/** The policy's own vocabulary, as the API serializes it. */
export type Band = "high" | "normal" | "low";
export type Lane = "escalated" | "reported" | "integrity" | "routine" | "quality_audit";
export type Sla = "on_track" | "approaching" | "overdue";

const BANDS: Band[] = ["high", "normal", "low"];
const LANES: Lane[] = ["escalated", "reported", "integrity", "routine", "quality_audit"];
const SLAS: Sla[] = ["on_track", "approaching", "overdue"];

/**
 * One reason a review sits where it does, written by the policy.
 *
 * `explanation` is prose the server composed; nothing here translates a code
 * into wording of its own. A code this build has never seen therefore still
 * renders correctly the day the server starts sending it, which is the point —
 * a console that silently drops unfamiliar reasons hides exactly the new signal
 * a moderator most needs to see.
 */
export type PriorityFactor = {
  code: string;
  observed: boolean | number | string;
  contribution: number;
  explanation: string;
};

/** The server's assessment of one card. Rendered, never recomputed. */
export type QueuePriority = {
  policy_version: string;
  lane: string;
  score: number;
  band: string;
  sla_state: string;
  due_at: string;
  factors?: PriorityFactor[];
};

/** The canonical server-side filters, exactly as the URL carries them. */
export type QueueFilters = {
  band: Band | "";
  lane: Lane | "";
  sla: Sla | "";
  factor: string;
  q: string;
  limit: number;
  offset: number;
};

export const DEFAULT_LIMIT = 50;

/** The page sizes the console offers, and the only ones a URL may ask for. */
export const QUEUE_LIMITS = [10, 25, 50, 100];

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
  /** The canonical assessment (design section 5). A sibling of `signals`. */
  priority: QueuePriority;
  /**
   * Which review timestamp stood in for the queue-entry time the schema does
   * not have yet: `created_at` for an initial pending review, `updated_at` for
   * a monetized-but-edited one. The UI must not present either as precise
   * lifecycle timing, which is what `QUEUE_TIME_APPROXIMATE` is for.
   */
  queue_time_basis?: string;
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
 * The band the server assessed, as a label.
 *
 * This used to derive a band here from the advisory fraud signals: High if any
 * signal fired, else Normal if the receipt was unverified, else Low. That was a
 * moderation policy written in the browser, and it disagreed with both the
 * Overview's headline and the order the queue itself arrived in. The policy now
 * lives in `moderation_priority.py`, is applied to the whole backlog before the
 * page is cut, and this function's entire job is to title-case its answer.
 *
 * An unfamiliar band — a server ahead of this deploy — is title-cased and shown
 * as-is. Substituting a band we recognise would misreport the queue; showing
 * nothing would hide a row's standing altogether.
 */
export function priorityOf(item: QueueCard): string {
  return titleCase(item.priority?.band ?? "");
}

function titleCase(value: string): string {
  if (!value) return "";
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** The lane and SLA state as labels, on the same terms as the band. */
export function laneLabel(item: QueueCard): string {
  return titleCase(item.priority?.lane ?? "");
}

/**
 * The reasons behind the score, in the policy's own words.
 *
 * A missing explanation falls back to the code rather than rendering an empty
 * row: a factor that contributed to a review's placement must be legible even
 * when the wording is missing.
 */
export function factorLines(item: QueueCard): PriorityFactor[] {
  const factors = item.priority?.factors ?? [];
  return factors.map((factor) => ({
    ...factor,
    explanation: factor.explanation?.trim() ? factor.explanation : factor.code,
  }));
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

/*
 * `queueRows` and `paginate` used to live here. Both are gone, and their
 * absence is the contract.
 *
 * `queueRows` filtered by a band this module derived and re-sorted by
 * `created_at`. `paginate` then cut that re-ordered list. Every one of those is
 * a claim about the WHOLE backlog, and the browser holds one page of it — so
 * filtering to High hid the High rows that were on page two, and sorting by
 * date overruled a policy order that had already weighed lane, SLA and score.
 *
 * The server does all three now, over every candidate, before it cuts the page
 * (`referral_service.get_prioritized_queue`). The screen renders `items` in the
 * order they arrived and changes the URL to ask a different question.
 */

/* --------------------------------------------------------- SLA and timing */

/**
 * Why every age on this screen is an approximation, stated once.
 *
 * There is no queue-entry column yet. Priority is evaluated against the
 * review's `created_at` (or `updated_at`, for a monetized review edited since
 * its link was attached), which is when the review was WRITTEN, not when it
 * reached the queue. For an initial submission those are the same moment; for
 * anything requeued they are not. Saying so is the difference between an
 * approximate age and a wrong one.
 */
export const QUEUE_TIME_APPROXIMATE =
  "Queue age is approximate: it is measured from the review's created_at " +
  "(updated_at for an edited one), because no queue-entry timestamp is " +
  "recorded yet. Treat it as an age, not as lifecycle timing.";

/** Which timestamp this card's age came from, in words. */
export function queueTimeBasisLabel(item: QueueCard): string {
  return item.queue_time_basis === "review_updated_at"
    ? "measured from the last edit"
    : "measured from submission";
}

/**
 * How long this card has been waiting, on its own declared basis.
 *
 * A DURATION ("3h"), not a relative timestamp ("3h ago"). The panel reads
 * "Waiting 3h", and "Waiting 3h ago" is not a thing a queue can say.
 */
export function queueAgeLabel(item: QueueCard, now: number = Date.now()): string {
  const started = Date.parse(item.review.created_at);
  if (Number.isNaN(started)) return "";
  return durationLabel(Math.max(0, (now - started) / 1000));
}

/**
 * Where this card stands against its lane's SLA target.
 *
 * The state is the server's; only the wording is ours. `due_at` is what the
 * policy computed from the lane target, so the remaining or elapsed time is
 * arithmetic on a served value rather than a second SLA implementation.
 */
export function slaStat(
  item: QueueCard,
  now: number = Date.now(),
): { state: string; label: string; available: boolean; value: string } {
  const state = item.priority?.sla_state ?? "";
  const due = Date.parse(item.priority?.due_at ?? "");

  if (!state || Number.isNaN(due)) {
    return { state, label: "SLA", available: false, value: "" };
  }

  const deltaSeconds = Math.abs(now - due) / 1000;
  const span = durationLabel(deltaSeconds);
  const value =
    state === "overdue"
      ? `Overdue by ${span}`
      : state === "approaching"
        ? `Due in ${span}`
        : `On track — ${span} left`;

  return { state, label: titleCase(state), available: true, value };
}

/** "3h" / "47m" / "2d" — a span, not a point in time. */
function durationLabel(seconds: number): string {
  if (seconds < MINUTE) return `${Math.floor(seconds)}s`;
  if (seconds < HOUR) return `${Math.floor(seconds / MINUTE)}m`;
  if (seconds < DAY) return `${Math.floor(seconds / HOUR)}h`;
  return `${Math.floor(seconds / DAY)}d`;
}

/* ----------------------------------------------------------- URL filters */

/**
 * Read the canonical filters out of a URL.
 *
 * Anything the policy does not define is dropped rather than forwarded: a
 * hand-edited `?band=critical` narrows to "no band filter" instead of putting a
 * 422 on the moderator's screen, and nothing unvalidated is ever passed through
 * to the API.
 */
export function parseQueueFilters(params: URLSearchParams): QueueFilters {
  const oneOf = <T extends string>(allowed: T[], value: string | null): T | "" =>
    allowed.includes((value ?? "") as T) ? ((value ?? "") as T) : "";

  const limit = Number.parseInt(params.get("limit") ?? "", 10);
  const offset = Number.parseInt(params.get("offset") ?? "", 10);

  return {
    band: oneOf(BANDS, params.get("band")),
    lane: oneOf(LANES, params.get("lane")),
    sla: oneOf(SLAS, params.get("sla")),
    factor: (params.get("factor") ?? "").trim(),
    q: (params.get("q") ?? "").trim(),
    limit: QUEUE_LIMITS.includes(limit) ? limit : DEFAULT_LIMIT,
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  };
}

/** The query string for the API call. Only what is actually set is sent. */
export function queueApiQuery(filters: QueueFilters): string {
  const params = new URLSearchParams();
  if (filters.band) params.set("band", filters.band);
  if (filters.lane) params.set("lane", filters.lane);
  if (filters.sla) params.set("sla", filters.sla);
  if (filters.factor) params.set("factor", filters.factor);
  if (filters.q) params.set("q", filters.q);
  params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  return params.toString();
}

/**
 * A link to the same queue with one thing changed.
 *
 * Changing a filter resets the page, because an offset counted into one
 * filtered list means nothing in another; passing `offset` explicitly is how
 * pagination keeps it.
 */
export function queueHref(
  filters: QueueFilters,
  changes: Partial<QueueFilters> & { tab?: Tab } = {},
): string {
  const next: QueueFilters = {
    ...filters,
    ...changes,
    offset: "offset" in changes ? (changes.offset ?? 0) : 0,
  };
  const params = new URLSearchParams();
  if (changes.tab) params.set("tab", changes.tab);
  if (next.band) params.set("band", next.band);
  if (next.lane) params.set("lane", next.lane);
  if (next.sla) params.set("sla", next.sla);
  if (next.factor) params.set("factor", next.factor);
  if (next.q) params.set("q", next.q);
  if (next.limit !== DEFAULT_LIMIT) params.set("limit", String(next.limit));
  if (next.offset) params.set("offset", String(next.offset));
  const query = params.toString();
  return query ? `${QUEUE_ROUTE}?${query}` : QUEUE_ROUTE;
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

/** The console's four tabs, in the order the console draws them. */
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
 * EVERY canonical filter rides along, not just the band: coming back to a tab
 * that had quietly dropped the lane or the search would show a moderator a
 * wider queue than the one they left, with nothing on screen saying so. The
 * offset does not ride along — a page number counted into the list being left
 * behind means nothing in the one being opened.
 */
export function tabHref(tab: Tab, filters: QueueFilters): string {
  return queueHref(filters, { tab });
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
