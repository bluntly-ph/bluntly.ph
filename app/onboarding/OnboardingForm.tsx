"use client";

import Image from "next/image";
import { useActionState, useRef, useState } from "react";

import { completeOnboarding, type ProfileState } from "@/app/actions/profile";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

const EMPTY: ProfileState = {};

/**
 * Onboarding step 1 — "Who do we have here?"
 *
 * The Figma frame shows a 4-step wizard; only step 1 (handle + photo) has
 * backend support today, so this ships as a single step rather than a progress
 * bar that lies about how much is left.
 */
export function OnboardingForm({ currentUsername }: { currentUsername: string }) {
  const [state, formAction, pending] = useActionState(completeOnboarding, EMPTY);
  const [preview, setPreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <form action={formAction} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-[length:var(--text-xl)] font-semibold text-[var(--text-primary)]">
          Who do we have here?
        </h1>
        <p className="text-[length:var(--text-xs)] text-[var(--text-secondary)]">
          This is how the community will see you.
        </p>
      </div>

      <div className="flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="relative h-20 w-20 overflow-hidden rounded-[var(--radius-circle)] bg-[var(--base-gray-200)] ring-1 ring-[var(--line-hairline-30)]"
          aria-label="Upload a profile photo"
        >
          {preview ? (
            <Image src={preview} alt="" fill sizes="80px" className="object-cover" />
          ) : (
            <span
              aria-hidden="true"
              className="flex h-full w-full items-center justify-center text-[length:var(--text-xl)] text-[var(--text-muted)]"
            >
              +
            </span>
          )}
        </button>
        <input
          ref={fileRef}
          type="file"
          name="avatar"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            setPreview(file ? URL.createObjectURL(file) : null);
          }}
        />
        <span className="text-[length:var(--text-2xs)] text-[var(--text-muted)]">
          Tap to upload a photo — PNG, JPEG or WebP, up to 5 MB
        </span>
      </div>

      <TextField
        label="Username"
        name="username"
        defaultValue={currentUsername}
        adornment="@"
        pattern="[a-zA-Z0-9_]{3,32}"
        autoComplete="username"
        hint="3–32 characters: letters, numbers and underscores."
        error={state.fieldErrors?.username}
      />

      <TextField
        label="Display name"
        name="display_name"
        autoComplete="name"
        hint="Optional. Shown alongside your handle."
        error={state.fieldErrors?.display_name}
      />

      {state.error && !state.fieldErrors ? (
        <p
          role="alert"
          className="rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] px-4 py-3 text-[length:var(--text-xs)] text-[var(--accent-danger)]"
        >
          {state.error}
        </p>
      ) : null}

      <Button type="submit" fullWidth disabled={pending}>
        {pending ? "Saving…" : "Continue"}
      </Button>
    </form>
  );
}

export default OnboardingForm;
