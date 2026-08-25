/**
 * A deliberately coarse world map, drawn as inline SVG.
 *
 * WHY NOT A GLOBE. A 3D globe would mean shipping a WebGL library into an
 * operations page to communicate two numbers per location, and it hides half
 * the world at any moment — on a panel whose job is "where is traffic coming
 * from", a reader should not have to rotate anything to find out. The flat
 * projection shows every location at once and costs nothing.
 *
 * WHY NO MAP DEPENDENCY. Real cartographic outlines are tens of kilobytes of
 * coordinates for a picture rendered here at a few hundred pixels wide. The
 * silhouette below is a low-fidelity stand-in: enough for a reader to locate a
 * marker on the right continent, and honestly not more than that. It is
 * context for the markers, never a source of truth — the ranked list beside it
 * carries the actual numbers, and every marker states its own value.
 *
 * The viewBox is degrees: 360 wide, 180 tall, so a coordinate projects with
 * arithmetic rather than a projection library.
 */

/** Coarse landmass outlines as [longitude, latitude] rings. */
const LAND: [number, number][][] = [
  // North America
  [[-168, 65], [-160, 71], [-140, 70], [-125, 70], [-100, 73], [-85, 73],
   [-60, 58], [-52, 47], [-65, 45], [-70, 42], [-75, 35], [-81, 25],
   [-97, 26], [-105, 22], [-115, 30], [-125, 40], [-125, 48], [-135, 58],
   [-150, 60]],
  // Greenland
  [[-45, 60], [-55, 68], [-50, 78], [-30, 82], [-20, 75], [-25, 68], [-40, 60]],
  // South America
  [[-81, 8], [-60, 12], [-50, 0], [-35, -5], [-38, -15], [-48, -25],
   [-58, -35], [-65, -45], [-72, -52], [-75, -45], [-71, -30], [-70, -18],
   [-78, -5]],
  // Africa
  [[-17, 15], [-17, 28], [-10, 36], [10, 37], [25, 32], [35, 31], [43, 12],
   [51, 12], [42, -2], [40, -15], [35, -25], [25, -34], [18, -34], [12, -18],
   [9, 4], [-8, 5]],
  // Eurasia
  [[-10, 36], [0, 44], [5, 52], [-5, 58], [10, 64], [30, 70], [60, 73],
   [90, 75], [130, 73], [160, 70], [180, 66], [170, 60], [140, 52],
   [135, 45], [127, 38], [120, 30], [110, 20], [95, 15], [90, 22], [80, 10],
   [72, 20], [60, 25], [48, 30], [35, 31], [25, 32], [10, 37]],
  // Australia
  [[113, -22], [115, -34], [130, -32], [140, -38], [150, -37], [153, -27],
   [145, -15], [135, -12], [125, -14]],
];

export function project(longitude: number, latitude: number) {
  return { x: longitude + 180, y: 90 - latitude };
}

const toPath = (ring: [number, number][]) =>
  ring
    .map(([lon, lat], i) => {
      const { x, y } = project(lon, lat);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ") + " Z";

export type MapMarker = {
  key: string;
  label: string;
  latitude: number;
  longitude: number;
  /** 0..1 against the largest location, already normalised by the caller. */
  weight: number;
  valueLabel: string;
};

/**
 * Marker radius in degrees of the viewBox.
 *
 * Square-rooted so AREA tracks the value — the eye compares blobs by area, and
 * a linear radius makes a city with twice the traffic look four times as busy.
 * Bounded at both ends: a floor so a small location stays clickable and
 * visible, a ceiling so one dominant city cannot cover the map it is drawn on.
 */
const R_MIN = 2.2;
const R_MAX = 9;
const radiusFor = (weight: number) =>
  R_MIN + Math.sqrt(Math.max(0, Math.min(1, weight))) * (R_MAX - R_MIN);

export function WorldMap({ markers }: { markers: MapMarker[] }) {
  return (
    <svg
      viewBox="0 0 360 180"
      className="h-full w-full"
      role="img"
      aria-label={
        markers.length
          ? `World map showing request volume for ${markers.length} location${markers.length === 1 ? "" : "s"}. The ranked list below gives the same figures as text.`
          : "World map with no request locations to show."
      }
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Graticule, every 30 degrees. Faint on purpose: it gives the eye a
          frame of reference without competing with the markers. */}
      <g stroke="var(--color-border-subtle)" strokeWidth="0.3" opacity="0.5">
        {[30, 60, 90, 120, 150].map((y) => (
          <line key={`h${y}`} x1="0" y1={y} x2="360" y2={y} />
        ))}
        {[60, 120, 180, 240, 300].map((x) => (
          <line key={`v${x}`} x1={x} y1="0" x2={x} y2="180" />
        ))}
      </g>

      <g
        fill="var(--color-border-subtle)"
        stroke="var(--color-border-default)"
        strokeWidth="0.4"
        strokeLinejoin="round"
        opacity="0.85"
      >
        {LAND.map((ring, i) => (
          <path key={i} d={toPath(ring)} />
        ))}
      </g>

      {/* Largest last, so a small marker is never buried under a big one. */}
      {[...markers]
        .sort((a, b) => a.weight - b.weight)
        .map((m) => {
          const { x, y } = project(m.longitude, m.latitude);
          const r = radiusFor(m.weight);
          return (
            <g key={m.key}>
              <circle
                cx={x}
                cy={y}
                r={r}
                fill="var(--color-accent)"
                fillOpacity="0.28"
                stroke="var(--color-accent)"
                strokeWidth="0.6"
              >
                {/* Native tooltip: the value is reachable on hover without any
                    JavaScript, and screen readers announce it. */}
                <title>{`${m.label} — ${m.valueLabel}`}</title>
              </circle>
              <circle cx={x} cy={y} r={Math.min(1.2, r / 3)} fill="var(--color-accent)" />
            </g>
          );
        })}
    </svg>
  );
}
