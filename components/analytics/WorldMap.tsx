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
 * The viewBox is degrees, so a coordinate projects with arithmetic rather than
 * a projection library. It is cropped to the inhabited band (85N to 60S)
 * rather than the full sphere: the poles carry no traffic, and including them
 * shrinks every populated continent to make room for empty ocean.
 */

/** Coarse landmass outlines as [longitude, latitude] rings. */
const LAND: [number, number][][] = [
  // North America, including the Central American isthmus.
  [[-168, 66], [-165, 71], [-155, 71], [-130, 70], [-120, 72], [-100, 74],
   [-80, 73], [-72, 68], [-62, 60], [-56, 52], [-66, 48], [-70, 43],
   [-74, 39], [-76, 35], [-81, 31], [-80, 25], [-84, 22], [-88, 21],
   [-87, 16], [-83, 9], [-78, 8], [-83, 13], [-90, 16], [-97, 22],
   [-105, 20], [-112, 24], [-117, 32], [-124, 40], [-124, 48], [-132, 55],
   [-145, 60], [-155, 58], [-165, 60]],
  // Greenland
  [[-45, 60], [-55, 68], [-50, 78], [-30, 82], [-20, 75], [-25, 68], [-40, 60]],
  // South America
  [[-79, 9], [-72, 12], [-62, 11], [-52, 5], [-50, 0], [-44, -2], [-35, -5],
   [-38, -13], [-41, -22], [-48, -25], [-53, -34], [-58, -38], [-62, -41],
   [-65, -45], [-69, -52], [-75, -52], [-73, -45], [-73, -37], [-71, -30],
   [-70, -23], [-70, -18], [-75, -14], [-81, -6], [-80, 0], [-77, 4]],
  // Africa
  [[-17, 15], [-16, 21], [-12, 28], [-9, 32], [-6, 36], [3, 37], [11, 37],
   [20, 33], [25, 32], [32, 31], [35, 28], [38, 18], [43, 12], [48, 12],
   [51, 11], [45, 5], [41, -1], [40, -8], [40, -15], [35, -21], [32, -26],
   [27, -34], [20, -35], [18, -32], [14, -23], [12, -17], [9, -1], [9, 4],
   [3, 6], [-5, 5], [-10, 7], [-14, 11]],
  // Eurasia. Its southern edge is kept as one smooth boundary and the
  // peninsulas are drawn as their own shapes below: folding India and
  // Indochina into this ring makes it self-intersect, and the renderer draws
  // the crossing as a spike through the Indian Ocean.
  [[-10, 36], [-9, 43], [-2, 43], [0, 47], [-5, 49], [2, 51], [8, 54],
   [10, 57], [5, 59], [8, 63], [13, 65], [21, 70], [28, 71], [40, 68],
   [55, 68], [60, 71], [70, 73], [80, 73], [90, 75], [105, 76], [115, 73],
   [130, 72], [140, 73], [160, 70], [170, 66], [180, 65], [175, 62],
   [162, 60], [155, 57], [143, 53], [140, 46], [133, 43], [130, 37],
   [127, 35], [122, 31], [118, 24], [110, 20], [102, 18], [95, 21],
   [88, 24], [80, 25], [72, 25], [62, 25], [55, 27], [50, 30], [44, 38],
   [36, 36], [28, 37], [26, 40], [23, 38], [19, 40], [16, 38], [12, 44],
   [8, 44], [3, 43], [-2, 36]],
  // Indian subcontinent
  [[68, 24], [72, 20], [75, 14], [77, 8], [80, 13], [83, 18], [88, 22],
   [85, 25], [76, 25]],
  // Indochina and the Malay peninsula
  [[98, 20], [100, 13], [103, 5], [104, 1], [106, 9], [108, 16], [105, 21]],
  // Great Britain and Ireland
  [[-5, 50], [-6, 53], [-3, 55], [-5, 58], [-2, 58], [0, 54], [1, 51]],
  // Japan
  [[130, 32], [135, 34], [140, 36], [142, 40], [145, 44], [141, 45],
   [139, 41], [136, 37], [132, 34]],
  // Indonesia, roughly Sumatra through Java
  [[95, 5], [104, -2], [106, -6], [114, -8], [119, -9], [112, -7],
   [104, -5], [97, 2]],
  // The Philippines, where most of this site's real traffic resolves.
  [[120, 18], [124, 17], [126, 12], [126, 7], [122, 6], [120, 10],
   [118, 14]],
  // Madagascar
  [[43, -12], [50, -15], [50, -24], [45, -25], [43, -20]],
  // New Zealand
  [[173, -35], [178, -37], [177, -40], [174, -41], [173, -38]],
  [[172, -41], [174, -44], [170, -46], [167, -45], [170, -42]],
  // Australia
  [[113, -22], [114, -26], [115, -34], [118, -35], [123, -34], [129, -32],
   [134, -33], [138, -35], [141, -38], [146, -39], [150, -37], [153, -32],
   [153, -28], [151, -24], [146, -19], [142, -11], [136, -12], [132, -11],
   [129, -15], [125, -14], [122, -17], [117, -21]],
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
      viewBox="0 5 360 145"
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
        {[30, 60, 90, 120].map((y) => (
          <line key={`h${y}`} x1="0" y1={y} x2="360" y2={y} />
        ))}
        {[60, 120, 180, 240, 300].map((x) => (
          <line key={`v${x}`} x1={x} y1="5" x2={x} y2="150" />
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
