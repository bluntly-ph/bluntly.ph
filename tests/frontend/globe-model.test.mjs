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
