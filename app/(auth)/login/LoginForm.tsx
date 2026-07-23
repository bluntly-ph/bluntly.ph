"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { login, requestOtp, verifyOtp, type FormState } from "@/app/actions/auth";
import { Button } from "@/components/ui/Button";
import { OtpInput } from "@/components/ui/OtpInput";
import { TextField } from "@/components/ui/TextField";

const EMPTY: FormState = {};

/**
 * Login. Two equal paths, because the designs draw both: the mobile frame is a
 * passwordless email code, the desktop frame is email + password.
 */
export function LoginForm({ next }: { next: string }) {
  const [mode, setMode] = useState<"password" | "code">("password");

  return mode === "password" ? (
    <PasswordLogin next={next} onSwitch={() => setMode("code")} />
  ) : (
    <CodeLogin onSwitch={() => setMode("password")} />
  );
}

function PasswordLogin({ next, onSwitch }: { next: string; onSwitch: () => void }) {
  const [state, formAction, pending] = useActionState(login, EMPTY);

  return (
    <form action={formAction} className="flex flex-col gap-6">
      <Heading title="Welcome back" subtitle="Log in to keep reviewing." />
      <input type="hidden" name="next" value={next} />

      <TextField
        label="Email address"
        name="email"
        type="email"
        autoComplete="email"
        required
        error={state.fieldErrors?.email}
      />
      <TextField
        label="Password"
        name="password"
        type="password"
        autoComplete="current-password"
        required
        error={state.fieldErrors?.password}
      />

      <FormError state={state} />

      <Button type="submit" fullWidth disabled={pending}>
        {pending ? "Logging in…" : "Log in"}
      </Button>

      <div className="flex flex-col gap-3 text-center">
        <button
          type="button"
          onClick={onSwitch}
          className="text-[length:var(--text-xs)] text-[var(--accent-primary)] underline-offset-4 hover:underline"
        >
          Email me a code instead
        </button>
        <p className="text-[length:var(--text-xs)] text-[var(--text-secondary)]">
          {"No account? "}
          <Link
            href="/signup"
            className="text-[var(--accent-primary)] underline-offset-4 hover:underline"
          >
            Sign up
          </Link>
        </p>
      </div>
    </form>
  );
}

function CodeLogin({ onSwitch }: { onSwitch: () => void }) {
  const [sendState, sendAction, sending] = useActionState(requestOtp, EMPTY);
  const [verifyState, verifyAction, verifying] = useActionState(verifyOtp, EMPTY);

  if (!sendState.emailSent) {
    return (
      <form action={sendAction} className="flex flex-col gap-6">
        <Heading
          title="Let's get started!"
          // The Figma copy says "we'll text you a code" above an email field.
          // Email is what the backend actually sends (docs/DEVIATIONS.md #59).
          subtitle="We'll email you a code to verify it's really you"
        />
        <input type="hidden" name="purpose" value="login" />
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
        <button
          type="button"
          onClick={onSwitch}
          className="text-center text-[length:var(--text-xs)] text-[var(--accent-primary)] underline-offset-4 hover:underline"
        >
          Use a password instead
        </button>
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

/** Only shows form-level errors; field-level ones render on their input. */
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

export default LoginForm;
