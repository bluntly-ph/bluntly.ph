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
  role: "user" | "moderator" | "admin";
  membership_tier: string;
  reputation_score: string;
  trust_stage: number;
  trust_level_name: string | null;
  is_suspended: boolean;
  created_at: string;
};

export const getUser = cache(async (): Promise<SessionUser | null> => {
  const token = await getSessionToken();
  if (!token) return null;

  try {
    return await apiFetch<SessionUser>("/api/v1/auth/me", { token });
  } catch (error) {
    if (error instanceof ApiError && error.isAuthExpired) {
      // The token is dead and there is nothing to refresh with. Drop it so the
      // user isn't stuck re-failing every request with a cookie that can't work.
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

/** For pages that require a specific role. */
export async function requireRole(
  ...roles: SessionUser["role"][]
): Promise<SessionUser> {
  const user = await requireUser();
  if (!roles.includes(user.role)) redirect("/");
  return user;
}
