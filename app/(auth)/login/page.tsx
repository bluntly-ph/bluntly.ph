import type { Metadata } from "next";

import { SignupForm } from "../signup/SignupForm";

export const metadata: Metadata = {
  title: "Log in — bluntly",
};

/**
 * Log in reuses the same two steps as signup — the design draws one flow, and
 * the backend issues the same TokenResponse either way. `purpose` only changes
 * which code the backend mints and the copy at the foot of the sheet.
 *
 * `?next=` is set by proxy.ts when a guard bounces a signed-out user here; it is
 * threaded to verifyOtp so sign-in returns them to what they were trying to do.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return <SignupForm purpose="login" next={next} />;
}
