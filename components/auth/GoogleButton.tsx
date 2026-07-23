"use client";

import Image from "next/image";
import { useState } from "react";

import { Button } from "@/components/ui/Button";

/**
 * "Continue with Google" — drawn in the welcome frame.
 *
 * Google sign-in is NOT implemented: the backend has no OAuth endpoints and
 * wiring one needs a Google Cloud client id/secret that only the project owner
 * can create. Rather than render a button that silently does nothing, or hide
 * an element the design calls for, this says so plainly and points at the path
 * that does work.
 *
 * When the backend gains `/auth/oauth/google`, set NEXT_PUBLIC_GOOGLE_AUTH=1
 * and replace the fallback branch with the redirect.
 */
export function GoogleButton() {
  const enabled = process.env.NEXT_PUBLIC_GOOGLE_AUTH === "1";
  const [notice, setNotice] = useState(false);

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="onBrand"
        fullWidth
        onClick={() => {
          if (enabled) {
            window.location.href = "/api/bff/api/v1/auth/oauth/google";
            return;
          }
          setNotice(true);
        }}
        icon={
          <Image
            src="/google-icon.svg"
            alt=""
            width={20}
            height={20}
            aria-hidden="true"
          />
        }
      >
        Continue with Google
      </Button>

      {notice ? (
        <p
          role="status"
          className="text-center text-[12px] font-light text-[rgba(242,242,242,0.85)]"
        >
          Google sign-in isn&rsquo;t set up yet — sign up with your email below.
        </p>
      ) : null}
    </div>
  );
}

export default GoogleButton;
