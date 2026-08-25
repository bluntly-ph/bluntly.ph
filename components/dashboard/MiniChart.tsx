/**
 * The two charts the dashboard design uses: a filled area and a sparkline.
 *
 * Hand-drawn SVG rather than a charting library. These are small, fixed,
 * non-interactive shapes — the design's area chart is 310x111 and the
 * sparklines are 100x70 — and a charting dependency would be several times the
 * size of the code below for shapes with no axes, no legend and no tooltips.
 *
 * Both take an already-dense series: one point per day in the window,
 * including the days that were zero. That matters for honesty as much as for
 * looks — a line drawn only from the days that had activity closes the gaps
 * and implies steady earning that did not happen.
 */

export type Point = { day: string; amount: number };

/** A smooth path through the points, in a 0..w by 0..h box. */
function smoothPath(values: number[], w: number, h: number, pad = 2): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  // A flat series must not become a straight line pinned to the bottom of the
  // box — that reads as "zero" when the value may be a steady non-zero.
  const span = max - min || 1;
  const stepX = values.length > 1 ? w / (values.length - 1) : 0;
  const y = (v: number) => pad + (1 - (v - min) / span) * (h - pad * 2);

  const pts = values.map((v, i) => [i * stepX, y(v)] as const);
  if (pts.length === 1) return `M0 ${pts[0][1]} L${w} ${pts[0][1]}`;

  // Catmull-Rom to cubic Bezier: the design's line is visibly curved, and a
  // polyline through daily points reads as jagged noise at this size.
  let d = `M${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2[0].toFixed(2)} ${p2[1].toFixed(2)}`;
  }
  return d;
}

/**
 * The earnings area chart. Orange, filled, with a dot on the highest day —
 * which is what the design marks, and it is also the only point on an
 * unlabelled curve a reader can actually identify.
 */
export function AreaChart({
  points,
  label,
  className = "",
}: {
  points: Point[];
  label: string;
  className?: string;
}) {
  const w = 310;
  const h = 111;
  const values = points.map((p) => p.amount);
  const line = smoothPath(values, w, h);
  if (!line) return null;

  const max = Math.max(...values, 0);
  const peakIndex = values.lastIndexOf(max);
  const stepX = values.length > 1 ? w / (values.length - 1) : 0;
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const peakY = 2 + (1 - (max - min) / span) * (h - 4);
  const id = `area-${points.length}-${max}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={`h-full w-full ${className}`}
      role="img"
      aria-label={label}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L${w} ${h} L0 ${h} Z`} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke="var(--accent-primary)"
        strokeWidth="2"
        strokeLinecap="round"
        // `preserveAspectRatio="none"` stretches the box, which would stretch
        // the stroke with it. This keeps the line an even weight.
        vectorEffect="non-scaling-stroke"
      />
      {max > 0 ? (
        <circle
          cx={peakIndex * stepX}
          cy={peakY}
          r="4"
          fill="var(--accent-primary)"
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
    </svg>
  );
}

/** The per-review sparkline. Green, matching the design's list rows. */
export function Sparkline({
  points,
  label,
  className = "",
}: {
  points: Point[];
  label: string;
  className?: string;
}) {
  const w = 100;
  const h = 70;
  const values = points.map((p) => p.amount);
  const line = smoothPath(values, w, h, 6);
  if (!line) return null;
  const id = `spark-${points.length}-${Math.max(...values, 0)}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={`h-full w-full ${className}`}
      role="img"
      aria-label={label}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-success)" stopOpacity="0.20" />
          <stop offset="100%" stopColor="var(--accent-success)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L${w} ${h} L0 ${h} Z`} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke="var(--accent-success)"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
