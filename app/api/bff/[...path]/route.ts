import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { API_ORIGIN } from "@/lib/api/origin";
import { getSessionToken } from "@/lib/session";

/**
 * Backend-for-frontend forwarder.
 *
 * Client components (voting, pagination, live search) need to call the API, but
 * they must never hold the access token. They call `/api/bff/<path>` instead and
 * this handler attaches the credential server-side.
 *
 * It is a dumb pipe on purpose: no response reshaping, so the problem+json
 * contract reaches the client untouched and `lib/api/errors.ts` still applies.
 */

/**
 * Headers that must not be copied onto the upstream request.
 *
 * Hop-by-hop and length headers are per-connection. `cookie` is dropped
 * deliberately: the backend authenticates from the Bearer token this handler
 * attaches and has no use for the browser's cookies, so forwarding them would
 * hand the session credential to a second system for no reason.
 */
const STRIPPED = new Set([
  "host",
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "content-length",
  "cookie",
]);

async function forward(request: NextRequest, path: string[]) {
  const token = await getSessionToken();
  const target = `${API_ORIGIN}/${path.join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!STRIPPED.has(key.toLowerCase())) headers.set(key, value);
  });
  // Never let a caller-supplied Authorization header through — the cookie is
  // the only credential this app honours.
  headers.delete("authorization");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);

  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Backend unreachable",
        status: 503,
        detail: "Could not reach the API.",
        instance: `/${path.join("/")}`,
        code: "backend_unreachable",
      },
      { status: 503, headers: { "content-type": "application/problem+json" } },
    );
  }

  const outHeaders = new Headers(response.headers);
  outHeaders.delete("content-encoding");
  outHeaders.delete("content-length");

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: outHeaders,
  });
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Context) {
  return forward(request, (await ctx.params).path);
}
export async function POST(request: NextRequest, ctx: Context) {
  return forward(request, (await ctx.params).path);
}
export async function PATCH(request: NextRequest, ctx: Context) {
  return forward(request, (await ctx.params).path);
}
export async function PUT(request: NextRequest, ctx: Context) {
  return forward(request, (await ctx.params).path);
}
export async function DELETE(request: NextRequest, ctx: Context) {
  return forward(request, (await ctx.params).path);
}
