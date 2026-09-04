import {
  READER_COOKIE_MAX_AGE,
  READER_COOKIE_NAME,
  mintReaderId,
  validReaderId,
} from "./reader-id-policy.ts";

const MAX_BODY_BYTES = 4_096;
const MAX_INT32 = 2_147_483_647;
const UPSTREAM_TIMEOUT_MS = 3_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
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

async function cancelAndRelease(reader: ReadableStreamDefaultReader<Uint8Array>): Promise<void> {
  try {
    await reader.cancel();
  } catch {
    // A broken request stream remains a fail-open telemetry loss.
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Releasing a disturbed stream cannot change the browser-facing response.
    }
  }
}

async function readBodyWithinLimit(request: Request): Promise<string | null> {
  const body = request.body;
  if (!body) return null;

  const declaredLength = request.headers.get("content-length");
  if (declaredLength && /^\d+$/.test(declaredLength) && Number(declaredLength) > MAX_BODY_BYTES) {
    try {
      await cancelAndRelease(body.getReader());
    } catch {
      // getReader itself can fail for an already-disturbed body.
    }
    return null;
  }

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    reader = body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_BODY_BYTES) {
        await cancelAndRelease(reader);
        reader = undefined;
        return null;
      }
      chunks.push(value);
    }
  } catch {
    return null;
  } finally {
    if (reader) {
      try {
        reader.releaseLock();
      } catch {
        // A malformed stream must not escape the public 204 shield.
      }
    }
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

function isInt32(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= MAX_INT32;
}

function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

/** Rebuild the client contract so browser-supplied identity and metadata cannot cross the boundary. */
function clientPayload(value: unknown): ClientPayload | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const input = value as Record<string, unknown>;

  if (
    !validReaderId(input.impression_id) ||
    !validUuid(input.review_id) ||
    !isInt32(input.seq) ||
    !isInt32(input.active_ms) ||
    !isInt32(input.body_active_ms) ||
    !isInt32(input.wall_ms) ||
    !isInt32(input.scroll_pct) ||
    ![0, 25, 50, 75, 100].includes(input.scroll_pct)
  ) {
    return null;
  }

  for (const field of CLIENT_FIELDS.slice(7)) {
    if (input[field] !== null && !isInt32(input[field])) return null;
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
 * Injectable public telemetry boundary. The route entry supplies server-only
 * cookies, environment, and fetch; every outcome remains an empty 204.
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
