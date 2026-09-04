import { handleTelemetryRequest } from "@/lib/telemetry-route-handler";
import { READER_COOKIE_NAME } from "@/lib/reader-id-policy";

/** Next calls this only for POST; absent method exports retain the default 405 for every other verb. */
export async function POST(request: Request): Promise<Response> {
  const cookieStore = await (await import("next/headers")).cookies();
  const sessionCookieName = process.env.SESSION_COOKIE_NAME ?? "bluntly_session";
  return handleTelemetryRequest(request, {
    apiOrigin: process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL,
    ingestKey: process.env.TELEMETRY_INGEST_KEY,
    readerId: cookieStore.get(READER_COOKIE_NAME)?.value,
    sessionToken: cookieStore.get(sessionCookieName)?.value,
    fetch: globalThis.fetch,
  });
}
