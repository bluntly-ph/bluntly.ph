"use client";

import Image from "next/image";
import { useActionState, useEffect, useRef, useState } from "react";
import {
  CaretLeft,
  ChatCircle,
  Confetti,
  MagnifyingGlass,
} from "@phosphor-icons/react/dist/ssr";

import { completeOnboarding, type ProfileState } from "@/app/actions/profile";
import { StepBar } from "@/components/auth/StepBar";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { INTERESTS, REQUIRED_INTERESTS } from "@/lib/interests";
import { prepareImageForUpload } from "@/lib/image";

const EMPTY: ProfileState = {};

type Availability =
  | { state: "idle" | "checking" }
  | { state: "free" }
  | { state: "taken"; reason: string };

/**
 * Live username availability (BUG-018).
 *
 * The clash used to surface only when the whole wizard was submitted — four
 * steps after the name was chosen — forcing a full restart with a new one.
 *
 * Debounced because this fires per keystroke, and each response is matched to
 * the query that asked for it: replies can arrive out of order, and a stale
 * "taken" landing after a newer "free" would condemn a perfectly good name.
 */
function useUsernameAvailability(
  username: string,
  ownUsername: string,
): Availability {
  // Only the *answer* is state. Everything derivable from the current input is
  // computed during render, which keeps the effect free of synchronous setState
  // and its cascading re-render (react-hooks/set-state-in-effect).
  const [resolved, setResolved] = useState<{
    name: string;
    available: boolean;
    reason?: string;
  } | null>(null);

  const candidate = username.trim();
  // The prefilled handle is already this user's own — nothing to check.
  const checkable =
    Boolean(candidate) && candidate !== ownUsername && candidate.length >= 3;

  useEffect(() => {
    if (!checkable) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/bff/api/v1/users/username-available?username=${encodeURIComponent(candidate)}`,
        );
        if (cancelled || !res.ok) return;
        const body = (await res.json()) as { available: boolean; reason?: string };
        if (cancelled) return;
        // Stamped with the name it answered about: replies can land out of
        // order, and a stale "taken" arriving after a newer "free" would
        // condemn a perfectly good name.
        setResolved({ name: candidate, available: body.available, reason: body.reason });
      } catch {
        // A failed check must not block the flow — the server re-checks on
        // submit regardless, so silence is the safe answer here.
      }
    }, 400);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [candidate, checkable]);

  if (!candidate || candidate === ownUsername) return { state: "idle" };
  if (candidate.length < 3) {
    return { state: "taken", reason: "Usernames need at least 3 characters." };
  }
  if (resolved?.name !== candidate) return { state: "checking" };
  return resolved.available
    ? { state: "free" }
    : { state: "taken", reason: resolved.reason ?? "That username is taken." };
}

export type OnboardingUser = {
  username: string;
  avatarUrl: string | null;
  trustLevelName: string;
  trustStage: number;
  verifiedReviewCount: number;
};

/**
 * The four-step onboarding wizard from Page 1.
 *
 * Steps 1 and 2 collect data and are submitted together at the end; steps 3 and
 * 4 are informational. Keeping the submit at the end means a user who abandons
 * midway has not half-written their profile.
 */
export function OnboardingWizard({ user }: { user: OnboardingUser }) {
  const [step, setStep] = useState(1);
  const [username, setUsername] = useState(user.username);
  const [displayName, setDisplayName] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [avatar, setAvatar] = useState<File | null>(null);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(user.avatarUrl);
  const [state, formAction, pending] = useActionState(completeOnboarding, EMPTY);
  const fileRef = useRef<HTMLInputElement>(null);
  const availability = useUsernameAvailability(username, user.username);

  function toggleInterest(slug: string) {
    setInterests((current) =>
      current.includes(slug)
        ? current.filter((s) => s !== slug)
        : current.length >= REQUIRED_INTERESTS
          ? current
          : [...current, slug],
    );
  }

  return (
    <form
      action={formAction}
      className={[
        // Mobile: the frame — a single full-height column.
        "mx-auto flex min-h-dvh w-full max-w-[430px] flex-col",
        "bg-[var(--surface-app)] px-8 pb-10 pt-12",
        // Desktop: a centred card wide enough for the interests grid to sit in
        // four columns — at phone width it is two columns and eight tiles, which
        // on a wide screen would be a needless scroll.
        "lg:my-16 lg:min-h-0 lg:max-w-[46rem] lg:rounded-[20px]",
        "lg:bg-[var(--surface-card)] lg:p-12 lg:shadow-[var(--shadow-card)]",
      ].join(" ")}
    >
      {/* Collected across steps, submitted once at the end. */}
      <input type="hidden" name="username" value={username} />
      <input type="hidden" name="display_name" value={displayName} />
      <input type="hidden" name="interests" value={interests.join(",")} />

      <StepBar
        step={step}
        action={
          step === 3 ? (
            <button
              type="button"
              onClick={() => setStep(4)}
              className="text-[12px] text-[var(--text-secondary)] underline-offset-2 hover:underline"
            >
              Skip
            </button>
          ) : null
        }
      />

      {step === 1 ? (
        <StepIdentity
          username={username}
          setUsername={setUsername}
          displayName={displayName}
          setDisplayName={setDisplayName}
          preview={preview}
          fileRef={fileRef}
          onPick={async (file) => {
            // Shrink before it is ever submitted. The platform refuses a
            // request body over ~4.5MB with a bare 413, and a phone photo is
            // routinely larger — so the avatar an ordinary person picks is
            // exactly the one that fails, at the end of a four-step wizard.
            // Same fix as the review photo and receipt fields.
            if (!file) {
              setAvatar(null);
              setPreview(null);
              return;
            }
            const prepared = await prepareImageForUpload(file, "photo");
            setAvatarError(prepared.error ?? null);
            if (prepared.error) {
              setAvatar(null);
              setPreview(null);
              return;
            }
            setAvatar(prepared.file);
            setPreview(URL.createObjectURL(prepared.file));
          }}
          avatarError={avatarError}
          error={state.fieldErrors?.username}
          availability={availability}
        />
      ) : null}

      {step === 2 ? (
        <StepInterests selected={interests} onToggle={toggleInterest} />
      ) : null}

      {step === 3 ? <StepIntro /> : null}

      {step === 4 ? <StepDone user={user} username={username} /> : null}

      {state.error && !state.fieldErrors ? (
        <p
          role="alert"
          className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[12px] text-[var(--accent-danger)]"
        >
          {state.error}
        </p>
      ) : null}

      {/* A single action stretched across the full card width reads as a
          banner rather than a button, so it keeps the column width on desktop. */}
      <div className="mt-8 flex shrink-0 flex-col gap-3 lg:mx-auto lg:w-full lg:max-w-[24rem]">
        {step < 4 ? (
          <Button
            type="button"
            fullWidth
            disabled={
              (step === 1 &&
                (username.trim().length < 3 || availability.state === "taken")) ||
              (step === 2 && interests.length < REQUIRED_INTERESTS)
            }
            onClick={() => {
              // The avatar File cannot live in a hidden input, so it is copied
              // onto the real file input just before the final submit.
              if (step === 3 && avatar && fileRef.current) {
                const dt = new DataTransfer();
                dt.items.add(avatar);
                fileRef.current.files = dt.files;
              }
              setStep(step + 1);
            }}
          >
            Continue
          </Button>
        ) : (
          <Button type="submit" fullWidth disabled={pending}>
            {pending ? "Setting up…" : "Explore bluntly"}
          </Button>
        )}

        {/* Back (BUG-018). Without it, changing an answer from step 1 meant
            abandoning the wizard and starting the whole thing again. Nothing is
            submitted until the end, so stepping back is free. */}
        {step > 1 ? (
          <button
            type="button"
            onClick={() => setStep(step - 1)}
            className="inline-flex items-center justify-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <CaretLeft size={16} /> Back
          </button>
        ) : null}
      </div>
    </form>
  );
}

function StepIdentity({
  username,
  setUsername,
  displayName,
  setDisplayName,
  preview,
  fileRef,
  onPick,
  avatarError,
  error,
  availability,
}: {
  username: string;
  setUsername: (v: string) => void;
  displayName: string;
  setDisplayName: (v: string) => void;
  preview: string | null;
  fileRef: React.RefObject<HTMLInputElement | null>;
  onPick: (file: File | null) => void | Promise<void>;
  avatarError?: string | null;
  error?: string;
  availability: Availability;
}) {
  return (
    <div className="flex flex-1 flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className="mt-6 text-[24px] font-semibold text-[var(--text-primary)]">
        Who do we have here?
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        This is how the community will see you.
      </p>

      <div className="mt-8 flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="relative h-[72px] w-[72px] overflow-hidden rounded-full border-2 border-[var(--text-primary)]"
          aria-label="Upload a profile photo"
        >
          {preview ? (
            <Image src={preview} alt="" fill sizes="72px" className="object-cover" />
          ) : (
            <svg viewBox="0 0 72 72" aria-hidden="true" className="h-full w-full">
              <circle cx="36" cy="28" r="11" fill="none" stroke="currentColor" strokeWidth="2.5" />
              <path
                d="M14 60c3-11 11-17 22-17s19 6 22 17"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              />
            </svg>
          )}
        </button>
        <input
          ref={fileRef}
          type="file"
          name="avatar"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
        <span className="text-[12px] text-[var(--text-muted)]">
          Tap to upload to photo
        </span>
        {avatarError ? (
          <span role="alert" className="text-[12px] text-[var(--accent-danger)]">
            {avatarError}
          </span>
        ) : null}
      </div>

      <div className="mt-8 flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            adornment="@"
            pattern="[a-z0-9_]{3,32}"
            autoComplete="username"
            placeholder="violewashere"
            // The server's verdict on submit still wins; this is the earlier,
            // friendlier warning (BUG-018).
            error={error ?? (availability.state === "taken" ? availability.reason : undefined)}
          />
          {!error && availability.state === "free" ? (
            <p className="text-[12px] text-[var(--accent-success)]">
              @{username} is available.
            </p>
          ) : null}
          {!error && availability.state === "checking" ? (
            <p className="text-[12px] text-[var(--text-muted)]">Checking…</p>
          ) : null}
        </div>
        <TextField
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          autoComplete="name"
          placeholder="Optional"
        />
      </div>
    </div>
  );
}

function StepInterests({
  selected,
  onToggle,
}: {
  selected: string[];
  onToggle: (slug: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <h1 className="mt-6 text-[24px] font-semibold text-[var(--text-primary)]">
        What do you shop for?
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        {`Pick ${REQUIRED_INTERESTS} interest to cater your feed`}
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {INTERESTS.map((interest) => {
          const isOn = selected.includes(interest.slug);
          return (
            <button
              key={interest.slug}
              type="button"
              aria-pressed={isOn}
              onClick={() => onToggle(interest.slug)}
              className={[
                "flex min-h-[104px] flex-col items-start gap-4 rounded-[var(--radius-sm)]",
                // White on the mobile gray surface; on the white desktop card
                // the fill flips so the tiles still read as cards.
                "bg-white p-4 text-left shadow-[var(--shadow-card)]",
                "lg:bg-[var(--surface-app)] lg:shadow-none",
                // The ring is an outline, not a shadow: the base shadow is
                // dropped at lg, and a shadow-based ring would go with it.
                "outline-offset-0 transition-[outline-color,background-color]",
                "duration-[var(--duration-fast)]",
                isOn
                  ? "outline outline-2 outline-[var(--accent-primary)]"
                  : "outline outline-1 outline-transparent hover:outline-[var(--line-hairline-30)]",
              ].join(" ")}
            >
              <span
                className={[
                  "flex h-9 w-9 items-center justify-center rounded-[10px]",
                  isOn
                    ? "bg-[var(--accent-primary)] text-white"
                    : "bg-[var(--base-gray-100)] text-[var(--text-primary)]",
                ].join(" ")}
              >
                <svg
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d={interest.icon} />
                </svg>
              </span>
              <span className="text-[14px] font-medium leading-tight text-[var(--text-primary)]">
                {interest.label}
              </span>
            </button>
          );
        })}
      </div>

      <p aria-live="polite" className="mt-4 text-[12px] text-[var(--text-muted)]">
        {`${selected.length} of ${REQUIRED_INTERESTS} selected`}
      </p>
    </div>
  );
}

function StepIntro() {
  return (
    <div className="flex flex-1 flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className="mt-6 text-[24px] font-semibold text-[var(--text-primary)]">
        Introducing{" "}
        <span className="text-[var(--accent-primary)]">bluntly.ph</span>
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        A sneak peak for what&rsquo;s about to come
      </p>

      <div className="mt-10 flex flex-col items-center gap-8">
        <div
          aria-hidden="true"
          className="relative grid h-[140px] w-[140px] place-items-center rounded-full bg-[image:var(--brand-gradient)] text-[var(--base-gray-100)] shadow-[var(--shadow-card)]"
        >
          <MagnifyingGlass size={56} weight="bold" />
          <span className="absolute -bottom-1 -right-1 grid h-11 w-11 place-items-center rounded-full bg-[var(--surface-card)] text-[var(--accent-primary)] shadow-[var(--shadow-card)]">
            <ChatCircle size={22} weight="fill" />
          </span>
        </div>
        <div className="text-center">
          <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
            Search or Ask
          </h2>
          <p className="mt-2 text-[14px] text-[var(--text-secondary)]">
            Look up a product or ask the community before you buy.
          </p>
        </div>
      </div>
    </div>
  );
}

function StepDone({
  user,
  username,
}: {
  user: OnboardingUser;
  username: string;
}) {
  const target = 1;
  const progress = Math.min(user.verifiedReviewCount / target, 1) * 100;

  return (
    <div className="flex flex-1 flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className="mt-6 text-[24px] font-semibold text-[var(--text-primary)]">
        {`You're all set, @${username}!`}
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        We know you&rsquo;ll do great things
      </p>

      <div className="mt-10 flex justify-center">
        <div
          aria-hidden="true"
          className="grid h-[110px] w-[110px] place-items-center rounded-full bg-[image:var(--brand-gradient)] text-[var(--base-gray-100)] shadow-[var(--shadow-card)]"
        >
          <Confetti size={48} weight="fill" />
        </div>
      </div>

      <div className="mt-8 rounded-[var(--radius-sm)] bg-white p-5 shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
            {user.trustLevelName}
          </h2>
          <span className="rounded-full bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] px-3 py-1 text-[11px] text-[var(--accent-primary)]">
            {`Level ${user.trustStage}`}
          </span>
        </div>
        <p className="mt-3 text-[13px] text-[var(--text-secondary)]">
          Post your first verified review to become a Contributor and unlock
          earnings.
        </p>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={target}
          aria-valuenow={user.verifiedReviewCount}
          className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-[var(--base-gray-150)]"
        >
          <span
            className="block h-full rounded-full bg-[var(--accent-primary)]"
            style={{ width: `${Math.max(progress, 6)}%` }}
          />
        </div>
        <p className="mt-2 text-[11px] text-[var(--text-muted)]">
          {`${user.verifiedReviewCount} of ${target} verified review to become Contributor`}
        </p>
      </div>
    </div>
  );
}

export default OnboardingWizard;
