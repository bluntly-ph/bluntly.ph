import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

/** Routes that require a session. */
const PROTECTED = ["/dashboard", "/profile", "/settings", "/admin"];

/** Routes that make no sense while already signed in. */
const AUTH_ONLY = ["/login", "/signup", "/welcome"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (!hasSession && PROTECTED.some((p) => pathname.startsWith(p))) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (hasSession && AUTH_ONLY.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Everything except Next internals and static assets. Running the proxy on
     * every image and font request is pure latency.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
