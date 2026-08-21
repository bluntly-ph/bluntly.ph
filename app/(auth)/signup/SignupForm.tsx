"use client";

import Link from "next/link";
import { useActionState, useEffect, useState } from "react";

import { AuthSheet } from "@/components/auth/AuthSheet";
import { Button } from "@/components/ui/Button";
import { OtpInput } from "@/components/ui/OtpInput";
import { TextField } from "@/components/ui/TextField";
import { requestOtp, verifyOtp, type FormState } from "@/app/actions/auth";

const EMPTY: FormState = {};

/**
 * Gap enforced between resends (BUG-016).
 *
 * The backend allows 5 sends per address per 15 minutes. Five impatient clicks
 * therefore burn the whole quota in seconds and lock the address out for the
 * rest of the window — which is exactly how QA got stranded. Spacing the button
 * out means the allowance lasts long enough to actually receive an email.
 */
const RESEND_COOLDOWN_SECONDS = 60;

/** 886 -> "14:46". */
function countdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * Email signup — the "Let's get started!" and "Enter the code" frames.
 *
 * The copy is the frames' own, with one correction: the design reads "We'll
 * text you a code" above an *email* field. Delivery is by email, so the word is
 * corrected rather than shipping a promise the product does not keep
 * (docs/DEVIATIONS.md #59).
 */
export function SignupForm({
  purpose,
  next,
}: {
  purpose: "signup" | "login";
  /** Destination to return to after sign-in, from `?next=` (see proxy.ts). */
  next?: string;
}) {
  const [sendState, sendAction, sending] = useActionState(requestOtp, EMPTY);

  return sendState.emailSent ? (
    <CodeStep email={sendState.emailSent} purpose={purpose} next={next} />
  ) : (
    <form action={sendAction} className="contents">
      <AuthSheet
        footer={
          <Button type="submit" fullWidth disabled={sending}>
            {sending ? "Sending…" : "Send code"}
          </Button>
        }
      >
        <input type="hidden" name="purpose" value={purpose} />
        <h1 className="text-[20px] font-medium text-[var(--text-primary)]">
          Let&rsquo;s get started!
        </h1>
        <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
          We&rsquo;ll email you a code to verify it&rsquo;s really you
        </p>

        <div className="mt-6">
          <TextField
            label="Email address"
            labelHidden
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="Email address"
            required
            error={sendState.fieldErrors?.email}
          />
        </div>

        <FormError state={sendState} next={next} />

        <p className="mt-6 text-[12px] text-[var(--text-secondary)]">
          {purpose === "signup" ? "Already have an account? " : "New here? "}
          <Link
            href={withNext(purpose === "signup" ? "/login" : "/signup", next)}
            className="text-[var(--accent-primary)] underline underline-offset-2"
          >
            {purpose === "signup" ? "Log in" : "Sign up"}
          </Link>
        </p>
      </AuthSheet>
    </form>
  );
}

function CodeStep({
  email,
  purpose,
  next,
}: {
  email: string;
  purpose: "signup" | "login";
  next?: string;
}) {
  const [verifyState, verifyAction, verifying] = useActionState(verifyOtp, EMPTY);
  const [resendState, resendAction, resending] = useActionState(requestOtp, EMPTY);
  const [code, setCode] = useState("");
  // Reaching this step means a code was just sent, so the gap starts here — not
  // on the first resend. Otherwise the quota is one impatient click closer to
  // gone before the first email has even landed.
  const [waitSeconds, setWaitSeconds] = useState(RESEND_COOLDOWN_SECONDS);
  // useActionState hands back a fresh object per submit, so identity is what
  // separates "a new result arrived" from an unrelated re-render. Adjusting
  // state during render is React's sanctioned answer here — doing it in an
  // effect trips react-hooks/set-state-in-effect and costs an extra commit.
  const [handled, setHandled] = useState<FormState>(EMPTY);
  if (resendState !== handled) {
    setHandled(resendState);
    if (resendState.ok) {
      setWaitSeconds(RESEND_COOLDOWN_SECONDS);
    } else if (resendState.retryAfterSeconds) {
      // Honour what the server actually said rather than guessing; being told
      // "14:46" is the difference between waiting and giving up.
      setWaitSeconds(resendState.retryAfterSeconds);
    }
  }

  useEffect(() => {
    if (waitSeconds <= 0) return;
    const timer = setTimeout(() => setWaitSeconds((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [waitSeconds]);

  const waiting = waitSeconds > 0;

  return (
    <form action={verifyAction} className="contents">
      <AuthSheet
        footer={
          <Button
            type="submit"
            fullWidth
            // The frame draws Continue disabled until all six boxes are filled.
            disabled={verifying || code.length < 6}
          >
            {verifying ? "Verifying…" : "Continue"}
          </Button>
        }
      >
        <input type="hidden" name="email" value={email} />
        {/* Read by the resend action, which shares this form. */}
        <input type="hidden" name="purpose" value={purpose} />
        {/* Survives the OTP round-trip so verifyOtp can return the user to
            wherever the auth guard interrupted them. */}
        {next ? <input type="hidden" name="next" value={next} /> : null}
        <h1 className="text-[20px] font-medium text-[var(--text-primary)]">
          Enter the code
        </h1>
        <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
          Sent via your email address: {email}
        </p>
        {/* BUG-018: signing up with an address that already has an account gets
            a *login* code, and previously nothing said so — the reviewer was
            left waiting for a signup that silently became something else.
            Shown to everyone on this step rather than only when the address is
            taken, because which one it is must stay unrevealed: the server
            deliberately does not disclose account existence here. */}
        {purpose === "signup" ? (
          <p className="mt-2 text-[12px] text-[var(--text-muted)]">
            Already have an account with this address? The code above signs you
            in instead.
          </p>
        ) : null}

        <div className="mt-6">
          <OtpInput error={verifyState.error} onChangeValue={setCode} />
        </div>

        {/* A nested <form> is invalid HTML, so resend posts to its own action
            via formAction on a sibling submit button. */}
        <button
          type="submit"
          formAction={resendAction}
          formNoValidate
          disabled={resending || waiting}
          className="mt-3 self-start text-[12px] text-[var(--accent-primary)] underline-offset-2 hover:underline disabled:no-underline disabled:opacity-60"
        >
          {resending
            ? "Sending…"
            : waiting
              ? `Resend code in ${countdown(waitSeconds)}`
              : "Resend code"}
        </button>

        {/* Every one of these was previously invisible: the step rendered only
            the success line, so a 429 — or any failure — looked like nothing had
            happened at all, and the user kept clicking a spent allowance. */}
        {resendState.error ? (
          <p
            role="alert"
            className="mt-2 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-3 py-2 text-[12px] text-[var(--accent-danger)]"
          >
            {resendState.error}
            {/* Gated only on the server having sent a wait, not additionally on
                the local ticker being live: QA saw the message land without the
                time, and two conditions meant either one silently swallowed it.
                Falls back to the server's figure if the ticker hasn't started. */}
            {resendState.retryAfterSeconds
              ? ` You can request another in ${countdown(
                  waiting ? waitSeconds : resendState.retryAfterSeconds,
                )}.`
              : null}
          </p>
        ) : resendState.ok ? (
          <p role="status" className="mt-2 text-[12px] text-[var(--text-secondary)]">
            A new code is on its way. The code in any earlier email has stopped
            working — use the newest one.
          </p>
        ) : null}
      </AuthSheet>
    </form>
  );
}

/**
 * Carry `?next=` across a hop between the two auth pages.
 *
 * The switch link at the bottom of the sheet was hardcoded to `/login` and
 * `/signup`, so someone bounced from `/reviews/new` who chose "Sign up" rather
 * than logging in arrived without a destination and landed on the home page
 * afterwards, having lost what they were trying to do. `next` was preserved
 * only in `FormError`, which appears solely after an `account_not_found` error
 * — the one path where the user had *already* been told to switch.
 */
function withNext(href: string, next?: string): string {
  return next ? `${href}?next=${encodeURIComponent(next)}` : href;
}

function FormError({ state, next }: { state: FormState; next?: string }) {
  if (!state.error || state.fieldErrors) return null;
  const signupHref = withNext("/signup", next);
  return (
    <p
      role="alert"
      className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[12px] text-[var(--accent-danger)]"
    >
      {state.code === "account_not_found" ? (
        <>
          Looks like you don&apos;t have an account yet.{" "}
          <Link
            href={signupHref}
            className="font-semibold underline underline-offset-2"
          >
            Create an account
          </Link>{" "}
          to get started.
        </>
      ) : (
        state.error
      )}
    </p>
  );
}

export default SignupForm;
