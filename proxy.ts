import { NextResponse } from "next/server";
import type { NextProxy } from "next/server";

import { trafficBeacon } from "@/lib/traffic-beacon";

/**
 * Next 16 renamed Middleware to Proxy
 * (node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md).
 *
 * This is an OPTIMISTIC check only. It looks at cookie presence and nothing
 * else — it does not decode or validate the JWT. The Next docs are explicit
 * that proxy "should not be used as a full session management or authorization
 * solution"; that job belongs to lib/dal.ts, which verifies against the backend
 * on every request pass.
 *
 * The value here is avoiding a pointless render-then-redirect for signed-out
 * users, not security.
 */

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "bluntly_session";

/**
 * Routes that require a session.
 *
 * Every route guarded by `requireUser`/`requireRole` belongs here. Those guards
 * redirect to a bare `/login` because a Server Component cannot see its own
 * pathname — so a route missing from this list still ends up at the login page,
 * just without the `?next=` that brings the user back. Someone who clicks
 * "Write a review" while signed out should land on the review form after
 * signing in, not on the homepage.
 */
const PROTECTED = [
  "/dashboard",
  "/contracts",
  "/profile",
  "/settings",
  "/admin",
  "/moderate",
  "/onboarding",
  "/reviews/new",
  "/questions/new",
  "/requests/new",
];

/** Routes that make no sense while already signed in. */
const AUTH_ONLY = ["/login", "/signup", "/welcome"];

export const proxy: NextProxy = (request, event) => {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  // Traffic geography for the moderator panel. Handed to `waitUntil` so it
  // settles after the response is already on its way: analytics must never sit
  // on the critical path of a page load, and this one is allowed to fail
  // silently because a reader whose page rendered fine should never learn that
  // a counter did not increment.
  const beacon = trafficBeacon(request);
  if (beacon) event.waitUntil(beacon);

  if (!hasSession && PROTECTED.some((p) => pathname.startsWith(p))) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (hasSession && AUTH_ONLY.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
};

export const config = {
  matcher: [
    /*
     * Everything except Next internals and static assets. Running the proxy on
     * every image and font request is pure latency.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
