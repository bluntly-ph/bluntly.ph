import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { handleTelemetryRequest } from "../../lib/telemetry-route-handler.ts";
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
  assert.equal(Object.keys(payload).length, 13);
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

test("rejects UUID and int32-invalid known client fields before the private endpoint", async () => {
  let fetchCalls = 0;
  const invalidPayloads = [
    { ...payload, impression_id: "a04264e5-05b7-3a86-8ccd-0b3e3b25a18e" },
    { ...payload, review_id: "not-a-uuid" },
    { ...payload, seq: 2_147_483_648 },
    { ...payload, active_ms: 1.5 },
    { ...payload, body_active_ms: -1 },
    { ...payload, wall_ms: 2_147_483_648 },
    { ...payload, vote_after_ms: -1 },
    { ...payload, outlink_after_ms: 2_147_483_648 },
    { ...payload, scroll_pct: 42 },
  ];

  for (const invalid of invalidPayloads) {
    const response = await handleTelemetryRequest(
      request(invalid),
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
});

test("cancellation and lock-release failures remain fail-open", async () => {
  let fetchCalls = 0;
  const rejectedCancellation = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("x".repeat(4_097)));
    },
    cancel() {
      return Promise.reject(new Error("stream teardown failed"));
    },
  });
  const requestWithRejectedCancellation = new Request("https://bluntly.ph/api/telemetry", {
    method: "POST",
    headers: { "content-length": "4097" },
    body: rejectedCancellation,
    duplex: "half",
  });
  const noContentLengthOversized = new Request("https://bluntly.ph/api/telemetry", {
    method: "POST",
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("x".repeat(4_097)));
      },
    }),
    duplex: "half",
  });

  for (const input of [requestWithRejectedCancellation, noContentLengthOversized]) {
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
    assert.equal(await response.text(), "");
  }
  assert.equal(fetchCalls, 0);
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

test("uses only the server session for signed-in readers and never mints or forwards anonymous identity", async () => {
  let captured;
  const response = await handleTelemetryRequest(
    request(),
    options({
      sessionToken: "server-session-token",
      readerId: undefined,
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

test("a valid existing anonymous cookie is used but never refreshed", async () => {
  const response = await handleTelemetryRequest(
    request(),
    options({ fetch: async () => new Response(null, { status: 204 }) }),
  );
  assert.equal(response.status, 204);
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

test("invalid server forwarding headers remain behind the empty 204 shield", async () => {
  let fetchCalls = 0;
  const response = await handleTelemetryRequest(
    request(),
    options({
      ingestKey: "server-key\ninvalid-header-value",
      fetch: async () => {
        fetchCalls += 1;
        return new Response(null, { status: 204 });
      },
    }),
  );

  assert.equal(response.status, 204);
  assert.equal(await response.text(), "");
  assert.equal(fetchCalls, 0);
});

test("the route entry exposes only POST and binds the non-route handler", () => {
  const source = readFileSync(new URL("../../app/api/telemetry/route.ts", import.meta.url), "utf8");
  const exportLines = source.split("\n").filter((line) => line.startsWith("export "));

  assert.deepEqual(exportLines, ["export async function POST(request: Request): Promise<Response> {"]);
  assert.match(source, /handleTelemetryRequest/);
});

test("session boundaries delete the reader identity before session mutation", () => {
  const source = readFileSync(new URL("../../lib/session.ts", import.meta.url), "utf8");
  const create = source.slice(source.indexOf("export async function createSession"), source.indexOf("export async function getSessionToken"));
  const destroy = source.slice(source.indexOf("export async function destroySession"), source.indexOf("export async function setThemePreference"));
  const createClear = create.indexOf("clearReaderId(cookieStore)");
  const createSet = create.indexOf("cookieStore.set(COOKIE_NAME");
  const destroyClear = destroy.indexOf("clearReaderId(cookieStore)");
  const destroyDelete = destroy.indexOf("cookieStore.delete(COOKIE_NAME");

  assert.ok(createClear >= 0 && createSet >= 0 && createClear < createSet);
  assert.ok(destroyClear >= 0 && destroyDelete >= 0 && destroyClear < destroyDelete);
});
