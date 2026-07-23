import type { Metadata } from "next";

import { SignupForm } from "../signup/SignupForm";

export const metadata: Metadata = {
  title: "Log in — bluntly",
};

/**
 * Log in reuses the same two steps as signup — the design draws one flow, and
 * the backend issues the same TokenResponse either way. `purpose` only changes
 * which code the backend mints and the copy at the foot of the sheet.
 */
export default function LoginPage() {
  return <SignupForm purpose="login" />;
}
