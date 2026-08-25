import type { NextRequest } from "next/server";

/**
 * Report one page request's coarse location for the traffic panel.
 *
 * WHY IT LIVES IN THE PROXY. This is the only code path that sees a genuine
 * visitor request. Server-rendered pages reach the API through
 * `lib/api/client.ts`, which builds its headers from scratch and forwards none
 * of the visitor's — so a backend that read its own request headers would
 * record the location of the Vercel function on every render, and the chart
 * would show our own datacenter as the source of all traffic.
 *
 * WHAT IT COUNTS. Page requests, and only page requests. Not `/api/*`, not
 * prefetches, not asset requests. That makes the number one an operator can
 * actually interpret; mixing navigations with the XHR they trigger would
 * inflate a "busy" city purely because its readers clicked more.
 *
 * PRIVACY. The edge has already turned the address into a place, so no IP is
 * read, sent, or logged here. What leaves is a country, a coarse region/city,
 * the edge's own approximate coordinates for that city, and the serving POP.
 */

// The edge's geography headers. Absent off Vercel, which is why local
// development records nothing at all rather than inventing a location.
const H_COUNTRY = "x-vercel-ip-country";
const H_REGION = "x-vercel-ip-country-region";
const H_CITY = "x-vercel-ip-city";
const H_LAT = "x-vercel-ip-latitude";
const H_LON = "x-vercel-ip-longitude";
const H_ID = "x-vercel-id";

/** Reserved "unresolved" codes. `T1` is the Tor exit pseudo-country. */
const UNRESOLVED = new Set(["", "-", "xx", "zz", "t1"]);

function clean(value: string | null): string | undefined {
  const text = (value ?? "").trim();
  return !text || UNRESOLVED.has(text.toLowerCase()) ? undefined : text;
}

function coord(value: string | null): number | undefined {
  const text = clean(value);
  if (text === undefined) return undefined;
  const n = Number(text);
  // Dropped rather than clamped: a clamped coordinate is a made-up location.
  return Number.isFinite(n) && n >= -180 && n <= 180 ? n : undefined;
}

/**
 * Requests that must never be counted.
 *
 * `/api` first, and for two reasons: the beacon itself is an `/api/v1` request,
 * so counting them would make every page view recurse; and API calls are not
 * navigations.
 */
function isCountable(request: NextRequest): boolean {
  if (request.method !== "GET") return false;
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/api")) return false;
  // A prefetch is the browser guessing, not a person arriving.
  if (request.headers.get("next-router-prefetch")) return false;
  if (request.headers.get("purpose") === "prefetch") return false;
  // RSC payload fetches accompany a navigation already counted on its way in.
  if (request.nextUrl.searchParams.has("_rsc")) return false;
  return true;
}

/**
 * The beacon, or null when there is nothing worth reporting.
 *
 * Returns a promise the caller hands to `event.waitUntil` so it settles after
 * the response is already on its way — analytics must never be on the critical
 * path of a page load.
 */
export function trafficBeacon(request: NextRequest): Promise<unknown> | null {
  if (!isCountable(request)) return null;

  const country = clean(request.headers.get(H_COUNTRY));
  // No country means the edge could not place this request — off-platform, or
  // simply unresolved. Recording it as "unknown" would put a large permanent
  // bar in a chart whose only job is showing where traffic comes from.
  if (!country) return null;

  const vercelId = clean(request.headers.get(H_ID)) ?? "";
  const pop = vercelId.split("::", 1)[0]?.toLowerCase();
  const city = clean(request.headers.get(H_CITY));

  const body = JSON.stringify({
    country: country.toUpperCase(),
    region: clean(request.headers.get(H_REGION)),
    // Vercel percent-encodes city names; left encoded, `Ho%20Chi%20Minh`
    // ranks as a separate city from `Ho Chi Minh`.
    city: city ? safeDecode(city) : undefined,
    latitude: coord(request.headers.get(H_LAT)),
    longitude: coord(request.headers.get(H_LON)),
    pop: pop && /^[a-z0-9]{1,8}$/.test(pop) ? pop : undefined,
  });

  // Same-origin: `/api/v1/*` is rewritten to the backend service by
  // vercel.json, so this needs no API origin variable and no secret.
  const url = new URL("/api/v1/internal/traffic", request.url);

  // A failed beacon must never surface to the reader, whose page rendered
  // perfectly well. Swallowing is the correct behaviour, not laziness.
  return fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
    cache: "no-store",
    keepalive: true,
  }).catch(() => undefined);
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    // Malformed percent-encoding: keep the raw value rather than dropping a
    // real city because one byte was wrong.
    return value;
  }
}
