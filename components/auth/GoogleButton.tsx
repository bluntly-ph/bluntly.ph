"use client";

import { Button } from "@/components/ui/Button";
import { GoogleIcon } from "@/components/ui/GoogleIcon";

/**
 * "Continue with Google" — drawn in the welcome frame, and asked for on login
 * and signup by the owner (2026-09-16).
 *
 * Google sign-in is NOT implemented: the backend has no OAuth endpoints and
 * wiring one needs a Google Cloud client id and secret that only the project
 * owner can create. So the control is genuinely disabled rather than clickable:
 * it carries `disabled` and `aria-disabled`, it navigates nowhere, and a line
 * under it says why and where to go instead. A button that looks live and then
 * fails is worse than one that admits it is not ready.
 *
 * When the backend gains `/auth/oauth/google`, set NEXT_PUBLIC_GOOGLE_AUTH=1:
 * the same control becomes the redirect with no other change.
 */
export function GoogleButton({ purpose = "signup" }: { purpose?: "signup" | "login" }) {
  const enabled = process.env.NEXT_PUBLIC_GOOGLE_AUTH === "1";

  // Solid gray-100 reads as a raised control on the gradient; on the desktop
  // card it needs a hairline instead, or it disappears.
  const onCard =
    "lg:bg-[var(--surface-card)] lg:shadow-[inset_0_0_0_1px_var(--line-hairline-30)] lg:hover:bg-[var(--base-gray-100)]";

  if (!enabled) {
    return (
      <div className="flex flex-col gap-2">
        <Button
          variant="onBrand"
          fullWidth
          disabled
          aria-disabled="true"
          className={`${onCard} opacity-70`}
          icon={
            <span aria-hidden="true" className="opacity-60">
              <GoogleIcon />
            </span>
          }
        >
          Continue with Google
        </Button>
        <p className="text-center text-[12px] font-light text-[rgba(242,242,242,0.85)] lg:text-[var(--text-secondary)]">
          Coming soon — {purpose === "login" ? "log in" : "sign up"} with your email below.
        </p>
      </div>
    );
  }

  return (
    <Button
      variant="onBrand"
      fullWidth
      className={onCard}
      onClick={() => {
        window.location.href = "/api/bff/api/v1/auth/oauth/google";
      }}
      icon={<GoogleIcon />}
    >
      Continue with Google
    </Button>
  );
}

export default GoogleButton;
