"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import {
  register,
  requestOtp,
  verifyOtp,
  type FormState,
} from "@/app/actions/auth";
import { Button } from "@/components/ui/Button";
import { OtpInput } from "@/components/ui/OtpInput";
import { TextField } from "@/components/ui/TextField";

const EMPTY: FormState = {};

/**
 * Sign up. The mobile frame is passwordless (code by email); the desktop frame
 * is email + username + password. Both are offered at both breakpoints — the
 * account is the same either way — with the code path as the default because
 * it is the shorter route to a working account.
 */
export function SignupForm() {
  const [mode, setMode] = useState<"code" | "password">("code");

  return mode === "code" ? (
    <CodeSignup onSwitch={() => setMode("password")} />
  ) : (
    <PasswordSignup onSwitch={() => setMode("code")} />
  );
}

function CodeSignup({ onSwitch }: { onSwitch: () => void }) {
  const [sendState, sendAction, sending] = useActionState(requestOtp, EMPTY);
  const [verifyState, verifyAction, verifying] = useActionState(verifyOtp, EMPTY);

  if (!sendState.emailSent) {
    return (
      <form action={sendAction} className="flex flex-col gap-6">
        <Heading
          title="Let's get started!"
          subtitle="We'll email you a code to verify it's really you"
        />
        <input type="hidden" name="purpose" value="signup" />
        <TextField
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          required
          error={sendState.fieldErrors?.email}
        />
        <FormError state={sendState} />
        <Button type="submit" fullWidth disabled={sending}>
          {sending ? "Sending…" : "Send code"}
        </Button>
        <SwitchLink onClick={onSwitch}>Use a password instead</SwitchLink>
        <AlreadyHaveAccount />
      </form>
    );
  }

  return (
    <form action={verifyAction} className="flex flex-col gap-6">
      <Heading
        title="Check your email"
        subtitle={`We sent a 6-digit code to ${sendState.emailSent}. It expires in 10 minutes.`}
      />
      <input type="hidden" name="email" value={sendState.emailSent} />
      <OtpInput error={verifyState.error} />
      <Button type="submit" fullWidth disabled={verifying}>
        {verifying ? "Verifying…" : "Verify"}
      </Button>
    </form>
  );
}

function PasswordSignup({ onSwitch }: { onSwitch: () => void }) {
  const [state, formAction, pending] = useActionState(register, EMPTY);

  return (
    <form action={formAction} className="flex flex-col gap-6">
      <Heading
        title="Create an account"
        subtitle="Honest reviews start with a real account."
      />

      <TextField
        label="Email Address"
        name="email"
        type="email"
        autoComplete="email"
        required
        error={state.fieldErrors?.email}
      />
      <TextField
        label="Username"
        name="username"
        autoComplete="username"
        adornment="@"
        pattern="[a-zA-Z0-9_]{3,32}"
        hint="3–32 characters: letters, numbers and underscores. Leave blank and we'll pick one."
        error={state.fieldErrors?.username}
      />
      <TextField
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        hint="At least 8 characters."
        error={state.fieldErrors?.password}
      />

      <FormError state={state} />

      <Button type="submit" fullWidth disabled={pending}>
        {pending ? "Creating account…" : "Create Account"}
      </Button>

      <SwitchLink onClick={onSwitch}>Email me a code instead</SwitchLink>
      <AlreadyHaveAccount />
    </form>
  );
}

function Heading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-[length:var(--text-lg)] font-medium text-[var(--text-primary)]">
        {title}
      </h1>
      <p className="text-[length:var(--text-xs)] text-[var(--text-secondary)]">
        {subtitle}
      </p>
    </div>
  );
}

function SwitchLink({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-center text-[length:var(--text-xs)] text-[var(--accent-primary)] underline-offset-4 hover:underline"
    >
      {children}
    </button>
  );
}

function AlreadyHaveAccount() {
  return (
    <p className="text-center text-[length:var(--text-xs)] text-[var(--text-secondary)]">
      {"Already have an account? "}
      <Link
        href="/login"
        className="text-[var(--accent-primary)] underline-offset-4 hover:underline"
      >
        Log in
      </Link>
    </p>
  );
}

function FormError({ state }: { state: FormState }) {
  if (!state.error || state.fieldErrors) return null;
  return (
    <p
      role="alert"
      className="rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] px-4 py-3 text-[length:var(--text-xs)] text-[var(--accent-danger)]"
    >
      {state.error}
    </p>
  );
}

export default SignupForm;
