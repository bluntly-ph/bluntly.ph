import Link from "next/link";
import type { Metadata } from "next";

import { GoogleButton } from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = {
  title: "Join bluntly",
};

/**
 * Welcome.
 *
 * Mobile is Figma "Login & Signup" (5357:2982), read 2026-09-15, less its 48px
 * status bar: the wordmark 152px down the gradient; anchored to the bottom, the
 * promise — "Honest reviews. Real Payouts." in 24px SemiBold, 16px over the
 * line in 14px Light on 21px lines — 52px above "Continue with Google" and
 * "Sign up with email", 12px apart, then "Already have an account? Log in" in
 * 12px Light 12px under them and 43px above the bottom edge.
 *
 * On desktop the brand column already carries the wordmark and the promise, so
 * this side keeps only the actions, in a card. The `lg:` overrides on the two
 * buttons swap them from gradient-appropriate treatments (white fill / white
 * outline) to card-appropriate ones (hairline / solid brand), because the
 * surface underneath them changes.
 */
export default function WelcomePage() {
  return (
    <main className="flex flex-1 flex-col px-8 pb-[43px] text-[var(--base-gray-100)] lg:w-full lg:max-w-[26rem] lg:flex-none lg:rounded-[20px] lg:bg-[var(--surface-card)] lg:p-10 lg:text-[var(--text-primary)] lg:shadow-[var(--shadow-card)]">
      <div className="flex justify-center pt-[min(152px,18dvh)] lg:hidden">
        <Logo height={24} label="bluntly" />
      </div>
      <div aria-hidden="true" className="min-h-10 flex-1 lg:hidden" />

      <div className="flex flex-col gap-4 lg:gap-1">
        <h1 className="text-[24px] font-semibold leading-none lg:text-[22px] lg:leading-[1.25]">
          <span className="lg:hidden">
            Honest reviews.
            <br />
            Real Payouts.
          </span>
          <span className="hidden lg:inline">Create your account</span>
        </h1>
        <p className="text-[14px] font-light leading-[1.5] lg:text-[13px] lg:text-[var(--text-secondary)]">
          <span className="lg:hidden">
            Join Filipinos making smarter purchases and the reviewers earning from honest opinions.
          </span>
          <span className="hidden lg:inline">Honest reviews start with a real account.</span>
        </p>
      </div>

      <div className="mt-[52px] flex flex-col gap-3 lg:mt-7">
        <GoogleButton purpose="signup" />
        <Button
          href="/signup"
          variant="outline"
          fullWidth
          className="lg:border-transparent lg:bg-[var(--accent-primary)] lg:text-white lg:hover:bg-[var(--accent-primary-strong)]"
        >
          Sign up with email
        </Button>
      </div>

      <p className="mt-3 text-center text-[12px] font-light leading-none lg:mt-5">
        <span className="text-[rgba(242,242,242,0.7)] lg:text-[var(--text-secondary)]">Already have an account? </span>
        <Link
          href="/login"
          className="text-[var(--base-gray-100)] no-underline underline-offset-2 hover:underline lg:text-[var(--accent-primary)]"
        >
          Log in
        </Link>
      </p>
    </main>
  );
}
