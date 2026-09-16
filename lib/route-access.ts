/**
 * Which paths the proxy sends to /login when there is no session, and which it
 * sends home when there is one. Kept apart from proxy.ts so the site map's test
 * can check every page's declared access against the same rules the proxy runs.
 *
 * Every route guarded by `requireUser`/`requireRole` belongs in PROTECTED. Those
 * guards redirect to a bare `/login` because a Server Component cannot see its
 * own pathname — so a route missing from this list still ends up at the login
 * page, just without the `?next=` that brings the user back. Someone who clicks
 * "Write a review" while signed out should land on the review form after
 * signing in, not on the homepage.
 */
export const PROTECTED = [
  "/dashboard",
  "/contracts",
  "/profile",
  "/profile/edit",
  "/settings",
  "/admin",
  "/moderate",
  "/onboarding",
  "/reviews/new",
  "/questions/new",
  "/requests/new",
  // The seller composer, opened from the mobile action menu. Its page guards
  // with requireOnboardedUser, which alone would drop the return path.
  "/sellers/rate",
  // Reached from the avatar menu; its page guards with requireUser, which
  // alone sent a signed-out reader to a bare /login.
  "/notifications",
] as const;

/**
 * Protected paths with a dynamic segment, which a prefix cannot express. The
 * store dashboard guards with requireUser and was missing here, so a signed-out
 * owner lost the way back to their store (found building the site map).
 */
const PROTECTED_PATTERNS = [/^\/sellers\/[^/]+\/dashboard(?:\/|$)/];

/** Routes that make no sense while already signed in. */
export const AUTH_ONLY = ["/login", "/signup", "/welcome"] as const;

export function isProtectedPath(pathname: string): boolean {
  return (
    PROTECTED.some((prefix) => pathname.startsWith(prefix)) ||
    PROTECTED_PATTERNS.some((pattern) => pattern.test(pathname))
  );
}

export function isAuthOnlyPath(pathname: string): boolean {
  return AUTH_ONLY.some((prefix) => pathname.startsWith(prefix));
}
