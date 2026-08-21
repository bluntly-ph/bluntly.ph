import "server-only";

import { cache } from "react";
import { redirect } from "next/navigation";

import { apiFetch } from "./api/client";
import { ApiError } from "./api/errors";
import { destroySession, getSessionToken } from "./session";

/**
 * Data Access Layer.
 *
 * The Next docs are explicit that Proxy is not a session-management solution —
 * authorization belongs here, close to the data
 * (node_modules/next/dist/docs/01-app/02-guides/authentication.md §Creating a
 * Data Access Layer).
 *
 * `getUser` hits GET /auth/me on every request pass rather than decoding the
 * JWT, because roles are read from the DB per request: a promotion or a
 * suspension takes effect immediately, and a role baked into a stale token is
 * never trusted.
 *
 * React `cache` dedupes that call within a single render pass, so a layout and
 * three components asking for the user cost one request.
 */

export type SessionUser = {
  id: string;
  user_id: string | null;
  email: string;
  display_name: string | null;
  username: string | null;
  avatar_url: string | null;
  interests: string[] | null;
  role: "user" | "moderator" | "admin";
  membership_tier: string;
  reputation_score: string;
  trust_stage: number;
  trust_level_name: string | null;
  verified_review_count: number;
  is_suspended: boolean;
  created_at: string;
};

export const getUser = cache(async (): Promise<SessionUser | null> => {
  const token = await getSessionToken();
  if (!token) return null;

  try {
    return await apiFetch<SessionUser>("/api/v1/auth/me", { token });
  } catch (error) {
    if (
      error instanceof ApiError &&
      (error.isAuthExpired || error.code === "account_suspended")
    ) {
      // The token is dead and there is nothing to refresh with. Drop it so the
      // user isn't stuck re-failing every request with a cookie that can't work.
      //
      // A suspension is the same situation from the reader's side: the backend
      // refuses every authenticated request (security.get_current_user), so the
      // cookie cannot work again. Without this it threw instead, and a
      // suspended reader got a blank error boundary on every gated page —
      // correctly blocked, told nothing. Dropping the session sends them to
      // /login, where the login endpoint already answers "Account is
      // suspended." That is the explanation they were missing.
      //
      // Public pages were never affected: PageShell catches and renders
      // signed-out.
      await destroySession();
      return null;
    }
    throw error;
  }
});

/** For pages that require a session. Redirects instead of returning null. */
export const requireUser = cache(async (): Promise<SessionUser> => {
  const user = await getUser();
  if (!user) redirect("/login");
  return user;
});

/**
 * True once the account has been through the wizard.
 *
 * Interests are the reliable signal: the wizard's step 2 will not advance
 * without them, and nothing else writes the field, so their presence means the
 * whole flow ran. Username alone is not usable — OTP signup derives one
 * automatically, so every account has one from the moment it exists.
 */
export function isOnboarded(user: SessionUser): boolean {
  return Array.isArray(user.interests) && user.interests.length > 0;
}

/**
 * For pages an unfinished account has no business reaching.
 *
 * Signing up redirects to /onboarding, but that is a redirect, not a gate — a
 * new account could simply navigate away and use the site while the profile
 * data we asked for was never collected. This sends them back until it is.
 *
 * Reading stays open: the site is public, and bouncing someone out of a review
 * they were part-way through is worse than a late profile. It is *acting* —
 * writing a review, asking, requesting, banking earnings — that requires it.
 * Never call this from /onboarding itself; that redirects to itself forever.
 */
export const requireOnboardedUser = cache(async (): Promise<SessionUser> => {
  const user = await requireUser();
  if (!isOnboarded(user)) redirect("/onboarding");
  return user;
});

/** For pages that require a specific role. */
export async function requireRole(
  ...roles: SessionUser["role"][]
): Promise<SessionUser> {
  const user = await requireUser();
  if (!roles.includes(user.role)) redirect("/");
  return user;
}
