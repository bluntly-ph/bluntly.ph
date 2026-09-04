import assert from "node:assert/strict";
import test from "node:test";

import { handleTelemetryRequest } from "../../app/api/telemetry/route.ts";
import { READER_COOKIE_NAME } from "../../lib/reader-id-policy.ts";

const readerId = "9403e48c-7a4a-4c5c-8c84-4d5a64fc8bc7";
const payload = {
  impression_id: "a04264e5-05b7-4a86-8ccd-0b3e3b25a18e",
  review_id: "cb5fe8cf-87a8-4e37-a327-7585b2a8f20d",
  seq: 3,
  active_ms: 41_210,
  body_active_ms: 38_900,
  wall_ms: 61_004,
  scroll_pct: 75,
  vote_after_ms: null,
  report_after_ms: null,
  comment_after_ms: null,
  share_after_ms: null,
  photo_after_ms: null,
  outlink_after_ms: null,
};

function request(body = payload, headers = {}) {
  return new Request("https://bluntly.ph/api/telemetry", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-vercel-ip-country": " ph ",
      "user-agent": "Telemetry test browser",
      cookie: "bluntly_session=browser-secret",
      authorization: "Bearer browser-secret",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

function options(overrides = {}) {
  return {
    apiOrigin: "https://api.example.test/",
    ingestKey: "server-ingest-key",
    readerId,
    fetch: globalThis.fetch,
    ...overrides,
  };
}

test("forwards only the client telemetry allowlist with server-derived authority", async () => {
  let captured;
  const response = await handleTelemetryRequest(
    request({
      ...payload,
      user_id: "attacker",
      country: "US",
      timestamp: "2026-01-01T00:00:00Z",
      device_class: 3,
    }),
    options({
      fetch: async (url, init) => {
        captured = { url, init };
        return new Response(null, { status: 204 });
      },
    }),
  );

  assert.equal(response.status, 204);
  assert.equal(await response.text(), "");
  assert.equal(captured.url, "https://api.example.test/api/v1/internal/reading-telemetry");
  assert.deepEqual(Object.keys(JSON.parse(captured.init.body)).sort(), Object.keys(payload).sort());
  assert.deepEqual(JSON.parse(captured.init.body), payload);

  const headers = new Headers(captured.init.headers);
  assert.equal(headers.get("authorization"), null);
  assert.equal(headers.get("cookie"), null);
  assert.equal(headers.get("x-reader-anon"), readerId);
  assert.equal(headers.get("x-reader-country"), "PH");
  assert.equal(headers.get("user-agent"), "Telemetry test browser");
  assert.equal(headers.get("x-telemetry-key"), "server-ingest-key");
  assert.equal(headers.get("content-type"), "application/json");
  assert.equal(captured.init.cache, "no-store");
  assert.ok(captured.init.signal instanceof AbortSignal);
});

test("shields every upstream response and thrown transport error behind empty 204", async () => {
  for (const outcome of [422, 429, 500, new Error("offline")]) {
    const response = await handleTelemetryRequest(
      request(),
      options({
        fetch: async () => {
          if (outcome instanceof Error) throw outcome;
          return new Response("details", { status: outcome });
        },
      }),
    );

    assert.equal(response.status, 204);
    assert.equal(await response.text(), "");
  }
});

test("does not forward invalid or byte-oversized streamed request bodies", async () => {
  let fetchCalls = 0;
  let cancelled = false;
  const oversized = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("é".repeat(2_049)));
    },
    cancel() {
      cancelled = true;
    },
  });
  const oversizedRequest = new Request("https://bluntly.ph/api/telemetry", {
    method: "POST",
    headers: { "content-type": "application/json", "content-length": "5" },
    body: oversized,
    duplex: "half",
  });

  for (const input of [request("not-json"), oversizedRequest]) {
    const response = await handleTelemetryRequest(
      input,
      options({
        fetch: async () => {
          fetchCalls += 1;
          return new Response(null, { status: 204 });
        },
      }),
    );
    assert.equal(response.status, 204);
  }

  assert.equal(fetchCalls, 0);
  assert.equal(cancelled, true);
});

test("mints a private 24-hour cookie for signed-out readers", async () => {
  const previousNodeEnv = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  let response;
  try {
    response = await handleTelemetryRequest(
      request(),
      options({
        readerId: undefined,
        fetch: async () => new Response(null, { status: 204 }),
      }),
    );
  } finally {
    process.env.NODE_ENV = previousNodeEnv;
  }

  assert.equal(response.status, 204);
  assert.match(
    response.headers.get("set-cookie") ?? "",
    new RegExp(`^${READER_COOKIE_NAME}=[0-9a-f-]+; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax; Secure$`, "i"),
  );
});

test("uses only the server session for signed-in readers and omits anonymous identity", async () => {
  let captured;
  const response = await handleTelemetryRequest(
    request(),
    options({
      sessionToken: "server-session-token",
      fetch: async (_url, init) => {
        captured = init;
        return new Response(null, { status: 204 });
      },
    }),
  );

  const headers = new Headers(captured.headers);
  assert.equal(response.status, 204);
  assert.equal(headers.get("authorization"), "Bearer server-session-token");
  assert.equal(headers.get("x-reader-anon"), null);
  assert.equal(response.headers.get("set-cookie"), null);
});

test("missing server configuration fails silently without an upstream request", async () => {
  let fetchCalls = 0;
  for (const config of [{ apiOrigin: "" }, { ingestKey: "  " }]) {
    const response = await handleTelemetryRequest(
      request(),
      options({
        ...config,
        fetch: async () => {
          fetchCalls += 1;
          return new Response(null, { status: 204 });
        },
      }),
    );
    assert.equal(response.status, 204);
  }
  assert.equal(fetchCalls, 0);
});
