"use client";

import { Button } from "@/components/ui/Button";
import { GoogleIcon } from "@/components/ui/GoogleIcon";

/**
 * "Continue with Google" — drawn in the welcome frame, and asked for on login
 * and signup by the owner (2026-09-16).
 *
 * Google sign-in is NOT implemented, and the control says so instead of
 * pretending: `disabled`, `aria-disabled`, no navigation, and a line under it
 * pointing at the email form that does work. A button that looks live and then
 * fails is worse than one that admits it is not ready.
 *
 * WHY THERE IS NO FLAG HERE ANY MORE. This used to keep the live hand-off
 * behind `NEXT_PUBLIC_GOOGLE_AUTH`, ready for the day it was wanted. The
 * contract audit (`npm run audit:contract`) then reported that hand-off as the
 * one frontend call in the codebase with no operation behind it: the backend
 * publishes no OAuth route at all, so `/auth/oauth/google` is a 404 whatever
 * the flag says. A branch that cannot work is not readiness — it is a switch
 * that ships a broken sign-in the moment someone sets an environment variable,
 * on the screen where a failure is least recoverable and most alarming.
 *
 * TO ENABLE IT LATER, in this order: add the OAuth routes to the backend so
 * they appear in `docs/openapi.json`, set the Google Cloud client id and secret
 * (only the project owner can create those), then restore the redirect here.
 * It is a few lines, and it should be written against an endpoint that exists.
 */
export function GoogleButton({
  purpose = "signup",
  surface = "brand",
}: {
  purpose?: "signup" | "login";
  /**
   * What the button sits on. "brand": the welcome screen's gradient, where
   * white text reads. "sheet": the light AuthSheet of /login and /signup, where
   * it does not — on a phone the note under this button rendered
   * rgba(242,242,242,.85) on #f2f2f2 and could not be seen at all (measured
   * 2026-09-17 while comparing against Figma 5348:2789).
   */
  surface?: "brand" | "sheet";
}) {
  // Solid gray-100 reads as a raised control on the gradient; on the desktop
  // card it needs a hairline instead, or it disappears. On the light sheet the
  // design system's Secondary pill (ink hairline, no fill) is the light-surface
  // form of the same control — Button does not merge classes, so the surface
  // picks a variant rather than stacking a second background on this one.
  const onCard =
    "lg:bg-[var(--surface-card)] lg:shadow-[inset_0_0_0_1px_var(--line-hairline-30)] lg:hover:bg-[var(--base-gray-100)]";
  const note =
    surface === "sheet"
      ? "text-[var(--text-secondary)]"
      : "text-[rgba(242,242,242,0.85)] lg:text-[var(--text-secondary)]";

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant={surface === "sheet" ? "secondary" : "onBrand"}
        fullWidth
        disabled
        aria-disabled="true"
        className={`${surface === "sheet" ? "" : onCard} opacity-70`}
        icon={
          <span aria-hidden="true" className="opacity-60">
            <GoogleIcon />
          </span>
        }
      >
        Continue with Google
      </Button>
      <p className={`text-center text-[12px] font-light ${note}`}>
        Coming soon — {purpose === "login" ? "log in" : "sign up"} with your email below.
      </p>
    </div>
  );
}

export default GoogleButton;
