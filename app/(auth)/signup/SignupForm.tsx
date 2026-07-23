"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { AuthSheet } from "@/components/auth/AuthSheet";
import { Button } from "@/components/ui/Button";
import { OtpInput } from "@/components/ui/OtpInput";
import { TextField } from "@/components/ui/TextField";
import { requestOtp, verifyOtp, type FormState } from "@/app/actions/auth";

const EMPTY: FormState = {};

/**
 * Email signup — the "Let's get started!" and "Enter the code" frames.
 *
 * The copy is the frames' own, with one correction: the design reads "We'll
 * text you a code" above an *email* field. Delivery is by email, so the word is
 * corrected rather than shipping a promise the product does not keep
 * (docs/DEVIATIONS.md #59).
 */
export function SignupForm({ purpose }: { purpose: "signup" | "login" }) {
  const [sendState, sendAction, sending] = useActionState(requestOtp, EMPTY);

  return sendState.emailSent ? (
    <CodeStep email={sendState.emailSent} purpose={purpose} />
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

        <FormError state={sendState} />

        <p className="mt-6 text-[12px] text-[var(--text-secondary)]">
          {purpose === "signup" ? "Already have an account? " : "New here? "}
          <Link
            href={purpose === "signup" ? "/login" : "/signup"}
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
}: {
  email: string;
  purpose: "signup" | "login";
}) {
  const [verifyState, verifyAction, verifying] = useActionState(verifyOtp, EMPTY);
  const [resendState, resendAction, resending] = useActionState(requestOtp, EMPTY);
  const [code, setCode] = useState("");

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
        <h1 className="text-[20px] font-medium text-[var(--text-primary)]">
          Enter the code
        </h1>
        <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
          Sent via your email address: {email}
        </p>

        <div className="mt-6">
          <OtpInput error={verifyState.error} onChangeValue={setCode} />
        </div>

        {/* A nested <form> is invalid HTML, so resend posts to its own action
            via formAction on a sibling submit button. */}
        <button
          type="submit"
          formAction={resendAction}
          formNoValidate
          disabled={resending}
          className="mt-3 self-start text-[12px] text-[var(--accent-primary)] underline-offset-2 hover:underline disabled:opacity-60"
        >
          {resending ? "Sending…" : "Resend code"}
        </button>
        {resendState.ok ? (
          <p role="status" className="mt-2 text-[12px] text-[var(--text-secondary)]">
            A new code is on its way.
          </p>
        ) : null}
      </AuthSheet>
    </form>
  );
}

function FormError({ state }: { state: FormState }) {
  if (!state.error || state.fieldErrors) return null;
  return (
    <p
      role="alert"
      className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[12px] text-[var(--accent-danger)]"
    >
      {state.error}
    </p>
  );
}

export default SignupForm;
