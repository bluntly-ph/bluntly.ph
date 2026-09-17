import { NextResponse } from "next/server";
import type { NextProxy } from "next/server";

import { isAuthOnlyPath, isProtectedPath } from "@/lib/route-access";
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

// Which routes need a session, and which make no sense with one: lib/route-access.ts.

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

  if (!hasSession && isProtectedPath(pathname)) {
    const url = new URL("/login", request.url);
    // Path AND query. A route can carry its state in the query — the profile's
    // three sections are one route with a `?tab=` — and sending back only the
    // pathname lands the reader somewhere they did not ask for, quietly, after
    // they have done everything right. `safeNext` in app/actions/auth.ts
    // already resolves and revalidates whatever arrives here, keeping the
    // search and refusing anything that escapes the origin, so widening this
    // does not widen what a redirect can reach.
    url.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(url);
  }

  if (hasSession && isAuthOnlyPath(pathname)) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
};

export const config = {
  matcher: [
    {
      /*
       * Everything except Next internals and static assets. Running the proxy on
       * every image and font request is pure latency.
       */
      source: "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
      /*
       * ...and never on a PREFETCH — the router guessing where the reader might
       * go next, not a reader arriving. Measured on production (2026-09-17),
       * running the proxy on them did two kinds of damage:
       *
       * 1. The traffic beacon counted them. Next strips the Flight headers and
       *    `_rsc` from the request a proxy sees (node_modules/next/dist/server/
       *    web/adapter.js), so `isCountable` cannot tell a prefetch from a
       *    visit. Every review link that scrolled into view added a VIEW to that
       *    review: in one hour of lab runs that opened a single review, 24
       *    reviews gained 121 views, and the traffic panel counted 826 "page
       *    requests" for about 200 real page loads.
       *
       * 2. A signed-out reader's prefetch of a gated link (Write a review,
       *    Profile, Ask a question) was answered with a 307 to /login. The
       *    router replays a redirected prefetch with its cache-busting param and
       *    never cancels the first response ("TODO: We should abort the previous
       *    request", fetch-server-response.js), so those requests stayed open
       *    for the life of the page: Lighthouse's desktop runs of /feed and
       *    /search hit their 45 s load timeout waiting on them.
       *
       * Skipping prefetches here is the pattern the proxy docs give for exactly
       * this. It gives up nothing: every gated page guards itself on the server
       * (lib/dal.ts requireUser / requireOnboardedUser / requireRole), and the
       * real navigation — which has no prefetch header — still meets the proxy,
       * its redirect and its `?next=`.
       */
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
