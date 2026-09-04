const MAX_BODY_BYTES = 4_096;
const UPSTREAM_TIMEOUT_MS = 3_000;
const READER_COOKIE_NAME = "bluntly_rid";
const READER_COOKIE_MAX_AGE = 86_400;
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CLIENT_FIELDS = [
  "impression_id",
  "review_id",
  "seq",
  "active_ms",
  "body_active_ms",
  "wall_ms",
  "scroll_pct",
  "vote_after_ms",
  "report_after_ms",
  "comment_after_ms",
  "share_after_ms",
  "photo_after_ms",
  "outlink_after_ms",
] as const;

type ClientField = (typeof CLIENT_FIELDS)[number];
type ClientPayload = Record<ClientField, string | number | null>;

function validReaderId(value: unknown): value is string {
  return typeof value === "string" && UUID_V4.test(value);
}

function mintReaderId(): string {
  return crypto.randomUUID();
}

export type TelemetryRequestOptions = {
  apiOrigin?: string;
  ingestKey?: string;
  readerId?: string;
  sessionToken?: string | null;
  fetch?: typeof fetch;
};

function noContent(readerId?: string): Response {
  const headers = new Headers();
  if (readerId) {
    const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
    headers.set(
      "set-cookie",
      `${READER_COOKIE_NAME}=${readerId}; Path=/; Max-Age=${READER_COOKIE_MAX_AGE}; HttpOnly; SameSite=Lax${secure}`,
    );
  }
  return new Response(null, { status: 204, headers });
}

async function readBodyWithinLimit(request: Request): Promise<string | null> {
  const body = request.body;
  if (!body) return null;

  const declaredLength = request.headers.get("content-length");
  if (declaredLength && /^\d+$/.test(declaredLength) && Number(declaredLength) > MAX_BODY_BYTES) {
    const reader = body.getReader();
    try {
      await reader.cancel();
    } finally {
      reader.releaseLock();
    }
    return null;
  }

  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_BODY_BYTES) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } catch {
    return null;
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

/** Rebuild the client contract so browser-supplied identity and metadata cannot cross the boundary. */
function clientPayload(value: unknown): ClientPayload | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const input = value as Record<string, unknown>;

  if (
    typeof input.impression_id !== "string" ||
    typeof input.review_id !== "string" ||
    !isNonNegativeInteger(input.seq) ||
    !isNonNegativeInteger(input.active_ms) ||
    !isNonNegativeInteger(input.body_active_ms) ||
    !isNonNegativeInteger(input.wall_ms) ||
    !isNonNegativeInteger(input.scroll_pct) ||
    ![0, 25, 50, 75, 100].includes(input.scroll_pct)
  ) {
    return null;
  }

  for (const field of CLIENT_FIELDS.slice(7)) {
    if (input[field] !== null && !isNonNegativeInteger(input[field])) return null;
  }

  return {
    impression_id: input.impression_id,
    review_id: input.review_id,
    seq: input.seq,
    active_ms: input.active_ms,
    body_active_ms: input.body_active_ms,
    wall_ms: input.wall_ms,
    scroll_pct: input.scroll_pct,
    vote_after_ms: input.vote_after_ms as number | null,
    report_after_ms: input.report_after_ms as number | null,
    comment_after_ms: input.comment_after_ms as number | null,
    share_after_ms: input.share_after_ms as number | null,
    photo_after_ms: input.photo_after_ms as number | null,
    outlink_after_ms: input.outlink_after_ms as number | null,
  };
}

function countryFrom(request: Request): string | undefined {
  const country = request.headers.get("x-vercel-ip-country")?.trim();
  return country && /^[a-z]{2}$/i.test(country) ? country.toUpperCase() : undefined;
}

function upstreamOrigin(origin: string | undefined): string | undefined {
  const value = origin?.trim();
  if (!value) return undefined;
  try {
    return new URL(value).origin;
  } catch {
    return undefined;
  }
}

/**
 * Public, browser-facing telemetry boundary. It deliberately reveals nothing
 * about validation or backend availability: every outcome is an empty 204.
 */
export async function handleTelemetryRequest(
  request: Request,
  options: TelemetryRequestOptions = {},
): Promise<Response> {
  const sessionToken = options.sessionToken?.trim() || undefined;
  const existingReaderId = validReaderId(options.readerId) ? options.readerId : undefined;
  const mintedReaderId = !sessionToken && !existingReaderId ? mintReaderId() : undefined;
  const response = noContent(mintedReaderId);

  const origin = upstreamOrigin(options.apiOrigin);
  const ingestKey = options.ingestKey?.trim();
  if (!origin || !ingestKey) return response;

  const text = await readBodyWithinLimit(request);
  if (text === null) return response;

  let rawPayload: unknown;
  try {
    rawPayload = JSON.parse(text);
  } catch {
    return response;
  }
  const body = clientPayload(rawPayload);
  if (!body) return response;

  const headers = new Headers({
    "content-type": "application/json",
    "x-telemetry-key": ingestKey,
  });
  const country = countryFrom(request);
  const userAgent = request.headers.get("user-agent")?.trim();
  if (country) headers.set("x-reader-country", country);
  if (userAgent) headers.set("user-agent", userAgent);
  if (sessionToken) {
    headers.set("authorization", `Bearer ${sessionToken}`);
  } else {
    headers.set("x-reader-anon", existingReaderId ?? mintedReaderId!);
  }

  try {
    await (options.fetch ?? fetch)(`${origin}/api/v1/internal/reading-telemetry`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch {
    // Telemetry is collection-only and must never affect a reader's page.
  }
  return response;
}

/** Next calls this only for POST; absent method exports retain the default 405 for every other verb. */
export async function POST(request: Request): Promise<Response> {
  const cookieStore = await (await import("next/headers")).cookies();
  const sessionCookieName = process.env.SESSION_COOKIE_NAME ?? "bluntly_session";
  return handleTelemetryRequest(request, {
    apiOrigin: process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL,
    ingestKey: process.env.TELEMETRY_INGEST_KEY,
    readerId: cookieStore.get(READER_COOKIE_NAME)?.value,
    sessionToken: cookieStore.get(sessionCookieName)?.value,
  });
}
