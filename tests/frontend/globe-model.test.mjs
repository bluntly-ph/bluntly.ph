import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_VISIBLE_LOCATIONS,
  formatAggregateValue,
  markerSize,
  selectVisibleLocations,
  toGlobeMarkers,
} from "../../components/analytics/globe-model.ts";

const location = (overrides = {}) => ({
  country: "PH",
  region: "NCR",
  city: "Manila",
  pop: "sin",
  latitude: 14.5995,
  longitude: 120.9842,
  request_count: 10,
  requests_per_second: 0.25,
  share: 0.5,
  ...overrides,
});

test("selectVisibleLocations returns a compact request-ranked top list", () => {
  const input = Array.from({ length: MAX_VISIBLE_LOCATIONS + 3 }, (_, index) =>
    location({ city: `City ${index}`, request_count: index + 1 }),
  );

  const result = selectVisibleLocations(input);

  assert.equal(result.visible.length, MAX_VISIBLE_LOCATIONS);
  assert.deepEqual(
    result.visible.map((item) => item.request_count),
    [9, 8, 7, 6, 5, 4],
  );
  assert.equal(result.hiddenLocationCount, 3);
  assert.equal(result.hiddenRequestCount, 6);
});

test("markerSize uses bounded area scaling", () => {
  assert.equal(markerSize(0), 0.035);
  assert.equal(markerSize(1), 0.12);
  assert.equal(markerSize(4), 0.12);
  assert.ok(markerSize(0.25) > markerSize(0));
  assert.ok(markerSize(0.25) < markerSize(1));
});

test("toGlobeMarkers excludes invalid coordinates and normalizes against the top request count", () => {
  const markers = toGlobeMarkers([
    location({ city: "Manila", request_count: 20 }),
    location({ city: "Cebu", latitude: 10.3157, longitude: 123.8854, request_count: 5 }),
    location({ city: "Unknown", latitude: null, longitude: null, request_count: 100 }),
  ]);

  assert.equal(markers.length, 2);
  assert.deepEqual(markers[0].location, [14.5995, 120.9842]);
  assert.equal(markers[0].size, 0.12);
  assert.equal(markers[1].size, markerSize(0.25));
});

test("formatAggregateValue keeps the compact other row consistent with the selected metric", () => {
  assert.equal(formatAggregateValue(25, 100, "count"), "25");
  assert.equal(formatAggregateValue(25, 100, "rps"), "0.250/s");
  assert.equal(formatAggregateValue(250, 100, "rps"), "2.50/s");
  assert.equal(formatAggregateValue(25, 0, "rps"), "0.000/s");
});

test("toGlobeMarkers returns nothing for an empty dataset rather than throwing", () => {
  assert.deepEqual(toGlobeMarkers([]), []);
  const empty = selectVisibleLocations([]);
  assert.deepEqual(empty.visible, []);
  assert.equal(empty.hiddenLocationCount, 0);
  assert.equal(empty.hiddenRequestCount, 0);
});

test("toGlobeMarkers rejects coordinates that are out of range or not finite", () => {
  const rejected = [
    location({ latitude: 91, longitude: 0 }),
    location({ latitude: -91, longitude: 0 }),
    location({ latitude: 0, longitude: 181 }),
    location({ latitude: 0, longitude: -181 }),
    location({ latitude: Number.NaN, longitude: 0 }),
    location({ latitude: 0, longitude: Number.POSITIVE_INFINITY }),
  ];

  assert.deepEqual(toGlobeMarkers(rejected), []);
  // A rejected row must not become the normalisation ceiling for a valid one.
  const mixed = toGlobeMarkers([
    location({ latitude: 91, longitude: 0, request_count: 1_000 }),
    location({ request_count: 4 }),
  ]);
  assert.equal(mixed.length, 1);
  assert.equal(mixed[0].size, markerSize(1));
});

test("selectVisibleLocations hides nothing when the dataset is under the limit", () => {
  const input = Array.from({ length: MAX_VISIBLE_LOCATIONS - 2 }, (_, index) =>
    location({ city: `City ${index}`, request_count: index + 1 }),
  );

  const result = selectVisibleLocations(input);

  assert.equal(result.visible.length, input.length);
  assert.equal(result.hiddenLocationCount, 0);
  assert.equal(result.hiddenRequestCount, 0);
});

test("the globe and the ranked list cannot disagree about which location leads", () => {
  // Both readings derive from the same rows, so the largest marker must belong
  // to the row the list ranks first. requests_per_second is request_count over
  // a window shared by every row, so the ordering holds under either metric.
  const rows = [
    location({ city: "Cebu", latitude: 10.3157, longitude: 123.8854, request_count: 5, requests_per_second: 0.05 }),
    location({ city: "Manila", request_count: 40, requests_per_second: 0.4 }),
    location({ city: "Davao", latitude: 7.1907, longitude: 125.4553, request_count: 12, requests_per_second: 0.12 }),
  ];

  const { visible } = selectVisibleLocations(rows);
  const markers = toGlobeMarkers(rows);

  assert.equal(visible[0].city, "Manila");
  assert.equal(markers.length, rows.length);
  const largest = markers.indexOf(
    markers.reduce((a, b) => (b.size > a.size ? b : a)),
  );
  assert.deepEqual(markers[largest].location, [14.5995, 120.9842]);

  const byCount = [...rows].sort((a, b) => b.request_count - a.request_count);
  const byRate = [...rows].sort((a, b) => b.requests_per_second - a.requests_per_second);
  assert.deepEqual(
    byCount.map((r) => r.city),
    byRate.map((r) => r.city),
  );
});
