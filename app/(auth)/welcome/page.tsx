import type { Metadata } from "next";
import Link from "next/link";

import { GoogleButton } from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = {
  title: "Join bluntly",
};

/**
 * Welcome — the first Login & Signup frame.
 *
 * Full-bleed gradient, wordmark floating in the upper third, and the value
 * proposition + actions anchored to the bottom.
 */
export default function WelcomePage() {
  return (
    <main className="flex flex-1 flex-col px-8 pb-8 text-[var(--base-gray-100)]">
      <div className="flex flex-1 items-center justify-center pt-24">
        <Logo height={24} label="bluntly" />
      </div>

      <div className="flex flex-col gap-2">
        <h1 className="text-[24px] font-semibold leading-[1.25]">
          Honest reviews.
          <br />
          Real Payouts.
        </h1>
        <p className="text-[14px] font-light tracking-[0.168px]">
          Join Filipinos making smarter purchases and the reviewers earning from
          honest opinions.
        </p>
      </div>

      <div className="mt-8 flex flex-col gap-3">
        <GoogleButton />
        <Link href="/signup" className="contents">
          <Button variant="outline" fullWidth>
            Sign up with email
          </Button>
        </Link>
      </div>

      <p className="mt-5 text-center text-[12px] font-light tracking-[0.144px]">
        <span className="text-[rgba(242,242,242,0.7)]">
          Already have an account?{" "}
        </span>
        <Link href="/login" className="underline underline-offset-2">
          Log in
        </Link>
      </p>
    </main>
  );
}
