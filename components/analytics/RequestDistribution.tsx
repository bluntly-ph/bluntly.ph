"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/Skeleton";

import {
  formatAggregateValue,
  selectVisibleLocations,
  toGlobeMarkers,
  type AnalyticsLocation,
} from "./globe-model";
import { TrafficGlobe } from "./TrafficGlobe";

/**
 * Where requests came from, as a map and a ranked list.
 *
 * The list is not a caption for the map — it is the primary reading, and the
 * map is context. That ordering is deliberate: it is what makes the panel
 * usable without colour vision, without a pointer, and with a screen reader,
 * and it is why every figure appears as text next to its bar rather than only
 * as a marker size.
 *
 * Counts come from the aggregate table the proxy fills. Nothing here is
 * seeded: with no traffic yet the panel says so plainly instead of drawing a
 * demonstration world.
 */

type Distribution = {
  window_start: string;
  window_end: string;
  covered_seconds: number;
  total_requests: number;
  requests_per_second: number;
  locations: AnalyticsLocation[];
  other_request_count: number;
  other_location_count: number;
  has_data: boolean;
  range: string;
  metric: string;
  retention_days: number;
};

type Metric = "count" | "rps";

const RANGES = [
  { key: "24h", label: "24H" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "90d", label: "90D" },
] as const;

/** Operational analytics, not a live tail. Frequent enough to be current,
 *  infrequent enough that leaving the tab open is not a load generator. */
const REFRESH_MS = 60_000;

/** Country codes to names, via the browser's own data rather than a shipped
 *  table of 250 entries. Falls back to the code where unsupported. */
function countryName(code: string | null): string {
  if (!code) return "Unknown";
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

function placeLabel(loc: AnalyticsLocation): string {
  const country = countryName(loc.country);
  // Country alone when there is no city. The edge's region field is a raw
  // subdivision code — "GT", "00", "NCR" — and "GT, South Africa" reads as
  // noise to anyone who does not already know the code. The city is the only
  // sub-country label worth showing.
  return loc.city ? `${loc.city}, ${country}` : country;
}

const nf = new Intl.NumberFormat("en-US");

function valueFor(loc: AnalyticsLocation, metric: Metric): string {
  return metric === "count"
    ? nf.format(loc.request_count)
    : `${loc.requests_per_second.toFixed(loc.requests_per_second < 1 ? 3 : 2)}/s`;
}

/** "over the last 3h 20m" — says what the rate is actually averaged over,
 *  rather than letting the range button imply a window we have no data for. */
function humanDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return m % 60 ? `${h}h ${m % 60}m` : `${h}h`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d}d ${h % 24}h` : `${d}d`;
}

export function RequestDistribution() {
  const [metric, setMetric] = useState<Metric>("count");
  const [range, setRange] = useState<string>("24h");
  const [data, setData] = useState<Distribution | null>(null);
  const [error, setError] = useState(false);
  // Bumped by Retry so the effect re-runs. A counter rather than a `loading`
  // flag because setting state synchronously inside an effect cascades an
  // extra render on every metric or range change.
  const [attempt, setAttempt] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(
        `/api/bff/api/v1/admin/analytics/request-distribution?metric=${metric}&range=${range}`,
        { cache: "no-store" },
      );
      if (!res.ok) throw new Error(String(res.status));
      // Both state writes happen after the await, never synchronously inside
      // the effect that calls this — that ordering is what keeps a metric or
      // range change to a single render instead of a cascading pair.
      setData((await res.json()) as Distribution);
      setError(false);
    } catch {
      // Deliberately no provider detail: an operator can act on "it failed,
      // retry", and cannot act on an upstream stack trace.
      setError(true);
    }
  }, [metric, range]);

  useEffect(() => {
    // `load` is a subscription to an external system (a polled HTTP
    // endpoint), which is the case this rule's own guidance permits. It flags
    // the call because it cannot see that every setState inside `load` runs
    // after an await, never synchronously in this body — the effect itself
    // sets no state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load, attempt]);

  // Derived, not stored: data we already hold is stale the moment the reader
  // picks a different metric or range, and deriving it keeps the skeleton in
  // step with the request without a second render.
  const loading = !data || data.range !== range || data.metric !== metric;

  // `<dialog>` rather than a hand-rolled overlay: it gives Escape-to-close,
  // focus containment and focus restoration from the platform, which is far
  // more likely to be right than a bespoke key handler.
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (expanded && !el.open) el.showModal();
    if (!expanded && el.open) el.close();
  }, [expanded]);

  const body = (
    <Panel
      data={data}
      loading={loading}
      error={error}
      metric={metric}
      onRetry={() => setAttempt((n) => n + 1)}
      expanded={expanded}
    />
  );

  return (
    <section
      aria-labelledby="request-distribution-heading"
      className="rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]"
    >
      <header className="flex flex-wrap items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-3 sm:px-5">
        <h2
          id="request-distribution-heading"
          className="mr-auto text-[15px] font-semibold text-[var(--text-primary)]"
        >
          Request distribution
        </h2>

        <MetricToggle metric={metric} onChange={setMetric} />
        <RangeToggle range={range} onChange={setRange} />

        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="rounded-[var(--radius-pill)] px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
        >
          Expand
        </button>
      </header>

      {/* Only one live globe at a time. When the dialog opens, the card copy
          unmounts before the expanded copy starts its WebGL loop. */}
      <div className="p-4 sm:p-5">{expanded ? null : body}</div>

      <dialog
        ref={dialogRef}
        onClose={() => setExpanded(false)}
        aria-label="Request distribution, expanded"
        className="w-[min(96vw,72rem)] rounded-[var(--radius-md)] bg-[var(--surface-card)] p-0 backdrop:bg-black/50"
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-subtle)] px-4 py-3 sm:gap-3 sm:px-5">
          <h2 className="w-full text-[15px] font-semibold text-[var(--text-primary)] sm:mr-auto sm:w-auto">
            Request distribution
          </h2>
          <MetricToggle metric={metric} onChange={setMetric} />
          <RangeToggle range={range} onChange={setRange} />
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="rounded-[var(--radius-pill)] px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
          >
            Close
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto p-5">{expanded ? body : null}</div>
      </dialog>
    </section>
  );
}

function MetricToggle({
  metric,
  onChange,
}: {
  metric: Metric;
  onChange: (m: Metric) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Metric"
      className="flex overflow-hidden rounded-[var(--radius-pill)] shadow-[var(--shadow-hairline-inset)]"
    >
      {(
        [
          ["count", "Count"],
          ["rps", "RPS"],
        ] as const
      ).map(([key, label]) => (
        <button
          key={key}
          type="button"
          // Selection is announced, not merely coloured.
          aria-pressed={metric === key}
          onClick={() => onChange(key)}
          className={`px-3 py-1.5 text-[12px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
            metric === key
              ? "bg-[var(--accent-primary)] text-[var(--text-on-brand)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function RangeToggle({
  range,
  onChange,
}: {
  range: string;
  onChange: (r: string) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Time range"
      className="flex overflow-hidden rounded-[var(--radius-pill)] shadow-[var(--shadow-hairline-inset)]"
    >
      {RANGES.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          aria-pressed={range === key}
          onClick={() => onChange(key)}
          className={`px-2.5 py-1.5 text-[12px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
            range === key
              ? "bg-[var(--accent-primary)] text-[var(--text-on-brand)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Panel({
  data,
  loading,
  error,
  metric,
  onRetry,
  expanded,
}: {
  data: Distribution | null;
  loading: boolean;
  error: boolean;
  metric: Metric;
  onRetry: () => void;
  expanded: boolean;
}) {
  if (loading && !data) return <PanelSkeleton />;

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 py-8">
        <p className="text-[14px] text-[var(--text-secondary)]">
          Unable to load request distribution.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-4 py-2 text-[13px] font-semibold text-[var(--text-on-brand)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="py-10 text-center">
        <p className="text-[14px] text-[var(--text-primary)]">
          No request location data for this period yet.
        </p>
        <p className="mx-auto mt-1 max-w-[34rem] text-[13px] text-[var(--text-secondary)]">
          Collection began when this panel shipped, so earlier traffic is not
          represented. Locations appear here as requests arrive.
        </p>
      </div>
    );
  }

  const top = Math.max(1, ...data.locations.map((location) => location.request_count));
  const markers = toGlobeMarkers(data.locations);
  const compact = selectVisibleLocations(data.locations);

  const headline =
    metric === "count"
      ? nf.format(data.total_requests)
      : `${data.requests_per_second.toFixed(data.requests_per_second < 1 ? 3 : 2)}/s`;

  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-[28px] font-bold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
          {headline}
        </p>
        <p className="text-[13px] text-[var(--text-secondary)]">
          {metric === "count" ? "page requests" : "average, "}
          {metric === "rps" ? (
            <>over {humanDuration(data.covered_seconds)} of data</>
          ) : null}
        </p>
      </div>

      {/* Desktop puts the fixed top list beside the globe; narrow screens stack
          them. Neither side creates an inner scroll region. */}
      <div
        className={`mt-4 grid gap-5 ${
          expanded
            ? "lg:grid-cols-[minmax(24rem,1.35fr)_minmax(17rem,0.65fr)]"
            : "lg:grid-cols-[minmax(20rem,1.15fr)_minmax(16rem,0.85fr)]"
        }`}
      >
        <div className="relative min-w-0 self-start overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-20 bg-gradient-to-b from-[var(--surface-app)] to-transparent" />
          <div className="mx-auto w-full max-w-[30rem] p-2 sm:p-4">
            <TrafficGlobe markers={markers} locationCount={markers.length} />
          </div>
        </div>

        <RankedList
          locations={compact.visible}
          hiddenLocationCount={compact.hiddenLocationCount + data.other_location_count}
          hiddenRequestCount={compact.hiddenRequestCount + data.other_request_count}
          coveredSeconds={data.covered_seconds}
          metric={metric}
          top={top}
        />
      </div>

      <p className="mt-4 text-[12px] text-[var(--text-muted)]">
        Aggregate page requests by approximate location, kept for{" "}
        {data.retention_days} days. No IP addresses or identities are stored.
      </p>
    </div>
  );
}

function RankedList({
  locations,
  hiddenLocationCount,
  hiddenRequestCount,
  coveredSeconds,
  metric,
  top,
}: {
  locations: AnalyticsLocation[];
  hiddenLocationCount: number;
  hiddenRequestCount: number;
  coveredSeconds: number;
  metric: Metric;
  top: number;
}) {
  return (
    <div className="min-w-0">
      <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
        Top locations
      </p>
      <ol className="flex min-w-0 flex-col gap-2.5">
      {locations.map((loc) => (
        <li key={`${loc.country}-${loc.region}-${loc.city}-${loc.pop}`}>
          <div className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--text-primary)]">
              {placeLabel(loc)}
            </span>
            <span className="shrink-0 text-[13px] font-semibold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
              {valueFor(loc, metric)}
            </span>
          </div>
          {/* The bar restates the number it sits under; it is never the only
              way to read the value. */}
          <div
            aria-hidden="true"
            className="mt-1 h-1.5 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-app)]"
          >
            <div
              className="h-full rounded-[var(--radius-pill)] bg-[var(--accent-primary)]"
              style={{ width: `${Math.max(2, (loc.request_count / top) * 100)}%` }}
            />
          </div>
          {loc.pop ? (
            // Labelled as infrastructure, never as the visitor's city: a
            // reader in Manila is normally served from Singapore.
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
              served via {loc.pop.toUpperCase()}
            </p>
          ) : null}
        </li>
      ))}

      {hiddenLocationCount > 0 ? (
        <li className="border-t border-[var(--border-subtle)] pt-2.5">
          <div className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--text-secondary)]">
              Other ({hiddenLocationCount} location
              {hiddenLocationCount === 1 ? "" : "s"})
            </span>
            <span className="shrink-0 text-[13px] text-[var(--text-secondary)] [font-variant-numeric:tabular-nums]">
              {formatAggregateValue(hiddenRequestCount, coveredSeconds, metric)}
            </span>
          </div>
        </li>
      ) : null}
      </ol>
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading request distribution</span>
      <Skeleton className="h-7 w-32" />
      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(20rem,1.15fr)_minmax(16rem,0.85fr)]">
        <Skeleton className="mx-auto aspect-square w-full max-w-[30rem]" />
        <div className="flex flex-col gap-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <Skeleton className="h-3.5 w-3/4" />
              <Skeleton className="h-1.5 w-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
