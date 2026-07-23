import type { Metadata } from "next";
import Link from "next/link";

import { GoogleButton } from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = {
  title: "Join bluntly",
};

/**
 * Welcome.
 *
 * Mobile is the frame as drawn: gradient, wordmark floating in the upper third,
 * promise and actions anchored to the bottom.
 *
 * On desktop the brand column already carries the wordmark and the promise, so
 * this side keeps only the actions, in a card. The `lg:` overrides on the two
 * buttons swap them from gradient-appropriate treatments (white fill / white
 * outline) to card-appropriate ones (hairline / solid brand), because the
 * surface underneath them changes.
 */
export default function WelcomePage() {
  return (
    <main className="flex flex-1 flex-col px-8 pb-8 text-[var(--base-gray-100)] lg:w-full lg:max-w-[26rem] lg:flex-none lg:rounded-[20px] lg:bg-[var(--surface-card)] lg:p-10 lg:text-[var(--text-primary)] lg:shadow-[var(--shadow-card)]">
      <div className="flex flex-1 items-center justify-center pt-24 lg:hidden">
        <Logo height={24} label="bluntly" />
      </div>

      <div className="flex flex-col gap-2 lg:gap-1">
        <h1 className="text-[24px] font-semibold leading-[1.25] lg:text-[22px]">
          <span className="lg:hidden">
            Honest reviews.
            <br />
            Real Payouts.
          </span>
          <span className="hidden lg:inline">Create your account</span>
        </h1>
        <p className="text-[14px] font-light tracking-[0.168px] lg:text-[13px] lg:text-[var(--text-secondary)]">
          <span className="lg:hidden">
            Join Filipinos making smarter purchases and the reviewers earning
            from honest opinions.
          </span>
          <span className="hidden lg:inline">
            Honest reviews start with a real account.
          </span>
        </p>
      </div>

      <div className="mt-8 flex flex-col gap-3 lg:mt-7">
        <GoogleButton />
        <Link href="/signup" className="contents">
          <Button
            variant="outline"
            fullWidth
            className="lg:border-transparent lg:bg-[var(--accent-primary)] lg:text-white lg:hover:bg-[var(--accent-primary-strong)]"
          >
            Sign up with email
          </Button>
        </Link>
      </div>

      <p className="mt-5 text-center text-[12px] font-light tracking-[0.144px]">
        <span className="text-[rgba(242,242,242,0.7)] lg:text-[var(--text-secondary)]">
          Already have an account?{" "}
        </span>
        <Link
          href="/login"
          className="underline underline-offset-2 lg:text-[var(--accent-primary)] lg:no-underline lg:hover:underline"
        >
          Log in
        </Link>
      </p>
    </main>
  );
}
