import "server-only";

import { cookies } from "next/headers";

/**
 * Session cookie handling.
 *
 * The backend issues an HS256 JWT and has **no refresh token**
 * (docs/FRONTEND_INTEGRATION.md §2). So the cookie's lifetime is pinned to the
 * token's own `expires_in`: when the cookie dies the token was already dead.
 *
 * httpOnly is the point of the whole BFF design — XSS cannot read this.
 */

const COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? "bluntly_session";
const THEME_COOKIE = "theme";

export async function createSession(
  accessToken: string,
  expiresInSeconds: number,
): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, accessToken, {
    httpOnly: true,
    // Secure breaks plain-http localhost, where the dev server runs.
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: expiresInSeconds,
  });
}

export async function getSessionToken(): Promise<string | null> {
  return (await cookies()).get(COOKIE_NAME)?.value ?? null;
}

export async function destroySession(): Promise<void> {
  (await cookies()).delete(COOKIE_NAME);
}

export async function setThemePreference(theme: "light" | "dark"): Promise<void> {
  (await cookies()).set(THEME_COOKIE, theme, {
    httpOnly: false, // read by nothing privileged; a UI preference only
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
}

export { COOKIE_NAME as SESSION_COOKIE_NAME };
