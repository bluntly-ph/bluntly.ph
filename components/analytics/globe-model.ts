export type AnalyticsLocation = {
  country: string | null;
  region: string | null;
  city: string | null;
  pop: string | null;
  latitude: number | null;
  longitude: number | null;
  request_count: number;
  requests_per_second: number;
  share: number;
};

export type GlobeMarker = {
  location: [number, number];
  size: number;
};

export type AnalyticsMetric = "count" | "rps";

/** The analytics card should be readable at a glance, not become a scrollable table. */
export const MAX_VISIBLE_LOCATIONS = 6;

const MIN_MARKER_SIZE = 0.035;
const MAX_MARKER_SIZE = 0.12;

export function markerSize(weight: number): number {
  const bounded = Math.max(0, Math.min(1, weight));
  return MIN_MARKER_SIZE + Math.sqrt(bounded) * (MAX_MARKER_SIZE - MIN_MARKER_SIZE);
}

export function selectVisibleLocations(
  locations: AnalyticsLocation[],
  limit = MAX_VISIBLE_LOCATIONS,
) {
  const ranked = [...locations].sort((a, b) => b.request_count - a.request_count);
  const visible = ranked.slice(0, limit);
  const hidden = ranked.slice(limit);

  return {
    visible,
    hiddenLocationCount: hidden.length,
    hiddenRequestCount: hidden.reduce((sum, item) => sum + item.request_count, 0),
  };
}

export function toGlobeMarkers(locations: AnalyticsLocation[]): GlobeMarker[] {
  const valid = locations.filter(
    (item): item is AnalyticsLocation & { latitude: number; longitude: number } =>
      item.latitude !== null &&
      item.longitude !== null &&
      Number.isFinite(item.latitude) &&
      Number.isFinite(item.longitude) &&
      item.latitude >= -90 &&
      item.latitude <= 90 &&
      item.longitude >= -180 &&
      item.longitude <= 180,
  );
  const top = Math.max(1, ...valid.map((item) => item.request_count));

  return valid.map((item) => ({
    location: [item.latitude, item.longitude],
    size: markerSize(item.request_count / top),
  }));
}

const numberFormatter = new Intl.NumberFormat("en-US");

export function formatAggregateValue(
  requestCount: number,
  coveredSeconds: number,
  metric: AnalyticsMetric,
): string {
  if (metric === "count") return numberFormatter.format(requestCount);
  const rate = coveredSeconds > 0 ? requestCount / coveredSeconds : 0;
  return `${rate.toFixed(rate < 1 ? 3 : 2)}/s`;
}
