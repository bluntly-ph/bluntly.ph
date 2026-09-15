"use client";

import Image from "next/image";
import { useActionState, useEffect, useRef, useState } from "react";
import {
  At,
  BriefcaseMetal,
  CarProfile,
  ChatCircleText,
  Circuitry,
  Confetti,
  Dress,
  HairDryer,
  HandCoins,
  Headphones,
  Heartbeat,
  House,
  MagnifyingGlass,
  ShieldCheck,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { completeOnboarding, type ProfileState } from "@/app/actions/profile";
import { StepBar } from "@/components/auth/StepBar";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { INTERESTS, REQUIRED_INTERESTS } from "@/lib/interests";
import { prepareImageForUpload } from "@/lib/image";
import { trustLevelName } from "@/lib/trust";

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
function useUsernameAvailability(username: string, ownUsername: string): Availability {
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
  const checkable = Boolean(candidate) && candidate !== ownUsername && candidate.length >= 3;

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

/** Figma "InterestTile" glyphs (Icon/Category, 6841:555..577), by interest. */
const INTEREST_ICONS: Record<string, Icon> = {
  "electronics-tech": Circuitry,
  "office-productivity": BriefcaseMetal,
  audio: Headphones,
  "home-living": House,
  beauty: HairDryer,
  "fashion-accessories": Dress,
  automotive: CarProfile,
  "health-fitness": Heartbeat,
};

/**
 * Step 3's four cards, in the frames' order (5371:3673, 5380:4077, 5380:4098,
 * 5380:4119). One correction: "Every reviews are screened thoroughly."
 */
const INTRO_SLIDES: { title: string; body: string; Icon: Icon }[] = [
  { title: "Search or Ask", body: "Look up a product or ask the community before you buy.", Icon: MagnifyingGlass },
  { title: "Shop confidently", body: "Every review is screened thoroughly.", Icon: ShieldCheck },
  { title: "Say it bluntly", body: "Share your experience. We’ll guide you how.", Icon: ChatCircleText },
  { title: "Help and earn", body: "You earn for each person you help", Icon: HandCoins },
];

const TITLE = "mt-[30px] text-[24px] font-semibold leading-none text-[var(--text-primary)]";
const SUBTITLE = "mt-4 text-[14px] font-light leading-none text-[var(--text-primary)]";
const RAIL_LINK =
  "text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)] underline-offset-2 hover:text-[var(--text-primary)] hover:underline";

/**
 * The four-step onboarding wizard, Figma "Login & Signup" 5369:3079 onward,
 * read 2026-09-15: the StepBar 63px down, the title 30px under it in 24px
 * SemiBold, the subtitle 16px lower in 14px Light, and the pill 32px above the
 * bottom edge — 32px side gutters throughout.
 *
 * Steps 1 and 2 collect data and are submitted together at the end; steps 3 and
 * 4 are informational. Keeping the submit at the end means a user who abandons
 * midway has not half-written their profile.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - "Back" beside the step label (BUG-018): the frames draw none, and without
 *    it changing an answer meant starting over.
 *  - An optional display name under the username, which the profile carries.
 *  - The illustration discs on steps 3 and 4 are empty grey placeholders in the
 *    file; each carries a glyph for what its card says.
 *  - Step 4's card names the stage that really unlocks earnings (Verified
 *    Buyer), not the frame's "Contributor".
 */
export function OnboardingWizard({ user }: { user: OnboardingUser }) {
  const [step, setStep] = useState(1);
  const [slide, setSlide] = useState(0);
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

  function finishIntro() {
    // The avatar File cannot live in a hidden input, so it is copied onto the
    // real file input on the way into the last step — by Continue or by Skip.
    if (avatar && fileRef.current) {
      const dt = new DataTransfer();
      dt.items.add(avatar);
      fileRef.current.files = dt.files;
    }
    setStep(4);
  }

  function goBack() {
    if (step === 3 && slide > 0) setSlide(slide - 1);
    else setStep(step - 1);
  }

  return (
    <form
      action={formAction}
      className={[
        // Mobile: the frame — a single full-height column.
        "mx-auto flex min-h-dvh w-full max-w-[430px] flex-col",
        "bg-[var(--surface-app)] px-8 pb-8 pt-[63px]",
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
          step > 1 ? (
            <span className="flex items-center gap-4">
              <button type="button" onClick={goBack} className={RAIL_LINK}>
                Back
              </button>
              {step === 3 ? (
                <button type="button" onClick={finishIntro} className={RAIL_LINK}>
                  Skip
                </button>
              ) : null}
            </span>
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

      {step === 2 ? <StepInterests selected={interests} onToggle={toggleInterest} /> : null}

      {step === 3 ? <StepIntro slide={slide} /> : null}

      {step === 4 ? <StepDone user={user} username={username} /> : null}

      {state.error && !state.fieldErrors ? (
        <p
          role="alert"
          className="mt-4 rounded-[12px] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[12px] leading-[18px] text-[var(--accent-danger)]"
        >
          {state.error}
        </p>
      ) : null}

      {/* A single action stretched across the full card width reads as a
          banner rather than a button, so it keeps the column width on desktop. */}
      <div className="mt-auto shrink-0 pt-8 lg:mx-auto lg:w-full lg:max-w-[24rem]">
        {/* Keyed so React replaces the element rather than flipping its type:
            the click that opens step 4 would otherwise land on a button that has
            already become type="submit" and send the wizard before the reader
            has seen the last step. */}
        {step < 4 ? (
          <Button
            key="continue"
            type="button"
            fullWidth
            disabled={
              (step === 1 && (username.trim().length < 3 || availability.state === "taken")) ||
              (step === 2 && interests.length < REQUIRED_INTERESTS)
            }
            onClick={() => {
              if (step === 3) {
                if (slide < INTRO_SLIDES.length - 1) setSlide(slide + 1);
                else finishIntro();
                return;
              }
              setStep(step + 1);
            }}
          >
            Continue
          </Button>
        ) : (
          <Button key="explore" type="submit" fullWidth disabled={pending}>
            {pending ? "Setting up…" : "Explore bluntly"}
          </Button>
        )}
      </div>
    </form>
  );
}

/** Phosphor UserCircle in a 2px line at 128px, as "Login & Signup" 5369:3079 draws it. */
function UserCircleOutline() {
  return (
    <svg viewBox="0 0 256 256" aria-hidden="true" className="h-full w-full" fill="none" stroke="currentColor" strokeWidth="4">
      <circle cx="128" cy="128" r="96" />
      <circle cx="128" cy="120" r="40" />
      <path d="M63.8 199.37a72 72 0 0 1 128.4 0" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Figma 5369:3079 / 5369:3194: a 128px UserCircle 37px under the subtitle — a
 * chosen photo fills its middle 100px disc — and "Tap to upload to photo" in
 * 10px Regular #8c8c8c tucked under it; 51px lower the UsernameField: "Username"
 * in 14px Medium, 8px over a 52px field in white at 30%, a 20px At glyph 8px
 * before the value.
 */
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
    <div className="flex flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className={TITLE}>Who do we have here?</h1>
      <p className={SUBTITLE}>This is how the community will see you.</p>

      <div className="mt-[37px] flex flex-col items-center">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="relative grid h-32 w-32 cursor-pointer place-items-center text-[var(--base-black)]"
          aria-label="Upload a profile photo"
        >
          {preview ? (
            <span className="relative h-[100px] w-[100px] overflow-hidden rounded-full">
              <Image src={preview} alt="" fill sizes="100px" className="object-cover" />
            </span>
          ) : (
            <UserCircleOutline />
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
        <span className="-mt-0.5 text-[10px] leading-none text-[var(--base-gray-400)]">Tap to upload to photo</span>
        {avatarError ? (
          <span role="alert" className="mt-2 text-[12px] text-[var(--accent-danger)]">
            {avatarError}
          </span>
        ) : null}
      </div>

      <div className="mt-[51px] flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            adornment={<At size={20} className="text-[var(--text-primary)]" />}
            pattern="[a-z0-9_]{3,32}"
            autoComplete="username"
            placeholder="username"
            fieldSize="lg"
            tone="soft"
            // The server's verdict on submit still wins; this is the earlier,
            // friendlier warning (BUG-018).
            error={error ?? (availability.state === "taken" ? availability.reason : undefined)}
          />
          {!error && availability.state === "free" ? (
            <p className="text-[12px] leading-none text-[var(--accent-success)]">@{username} is available.</p>
          ) : null}
          {!error && availability.state === "checking" ? (
            <p className="text-[12px] leading-none text-[var(--text-muted)]">Checking…</p>
          ) : null}
        </div>
        <TextField
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          autoComplete="name"
          placeholder="Optional"
          fieldSize="lg"
          tone="soft"
        />
      </div>
    </div>
  );
}

/**
 * Figma 5369:3269 / 5369:3516: 31px under the subtitle two columns of
 * InterestTile (6842:567) 12px apart under a 0 4px 2px shadow at 10% — 157x136
 * white at radius 12, 24px in, a 48px chip at radius 12 in the page colour
 * holding a 28px glyph, 12px over the label in 14px Medium on a two-line slot.
 * Chosen: a brand-orange line, the chip at the brand tint, the glyph in orange.
 * Once three are picked the subtitle becomes "Someone with taste, I see".
 */
function StepInterests({ selected, onToggle }: { selected: string[]; onToggle: (slug: string) => void }) {
  const done = selected.length >= REQUIRED_INTERESTS;
  return (
    <div className="flex flex-col">
      <h1 className={TITLE}>What do you shop for?</h1>
      <p className={SUBTITLE}>
        {done ? "Someone with taste, I see" : `Pick ${REQUIRED_INTERESTS} interest to cater your feed`}
      </p>

      <div className="mt-[31px] grid grid-cols-2 gap-3 drop-shadow-[0_4px_2px_rgba(0,0,0,0.1)] lg:grid-cols-4">
        {INTERESTS.map((interest) => {
          const isOn = selected.includes(interest.slug);
          const Glyph = INTEREST_ICONS[interest.slug] ?? Circuitry;
          return (
            <button
              key={interest.slug}
              type="button"
              aria-pressed={isOn}
              onClick={() => onToggle(interest.slug)}
              className={[
                "flex h-[136px] cursor-pointer flex-col items-start gap-3 rounded-[12px] border p-[23px] text-left",
                // White on the mobile gray surface; on the white desktop card
                // the fill flips so the tiles still read as cards.
                "bg-white lg:bg-[var(--surface-app)]",
                "transition-[border-color] duration-[var(--duration-fast)]",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]",
                isOn ? "border-[var(--accent-primary)]" : "border-transparent hover:border-[var(--line-hairline-30)]",
              ].join(" ")}
            >
              <span
                className={`grid h-12 w-12 shrink-0 place-items-center rounded-[12px] ${
                  isOn
                    ? "bg-[rgba(239,88,33,0.1)] text-[var(--accent-primary)]"
                    : "bg-[var(--surface-app)] text-[var(--text-primary)] lg:bg-white"
                }`}
              >
                <Glyph size={28} aria-hidden="true" />
              </span>
              <span className="h-7 text-[14px] font-medium leading-[14px] text-[var(--text-primary)]">
                {interest.label}
              </span>
            </button>
          );
        })}
      </div>

      <p aria-live="polite" className="sr-only">
        {`${selected.length} of ${REQUIRED_INTERESTS} selected`}
      </p>
    </div>
  );
}

/**
 * Figma 5371:3673 and its three siblings: "Introducing bluntly.ph" (the name in
 * brand orange); a 100px disc 58px under the subtitle; 139px lower the card's
 * title in 20px Medium, and 34px under it the line in 16px Light at 60%, 238px
 * wide, centred.
 */
function StepIntro({ slide }: { slide: number }) {
  const { title, body, Icon } = INTRO_SLIDES[Math.min(slide, INTRO_SLIDES.length - 1)];
  return (
    <div className="flex flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className={TITLE}>
        Introducing <span className="text-[var(--accent-primary)]">bluntly.ph</span>
      </h1>
      <p className={SUBTITLE}>A sneak peak for what&rsquo;s about to come</p>

      <div aria-live="polite" className="flex flex-col items-center text-center">
        <span
          aria-hidden="true"
          className="mt-[58px] grid h-[100px] w-[100px] place-items-center rounded-full bg-[var(--base-gray-200)] text-[var(--text-primary)]"
        >
          <Icon size={48} weight="light" />
        </span>
        <h2 className="mt-[139px] text-[20px] font-medium leading-none text-[var(--text-primary)]">{title}</h2>
        <p className="mt-[34px] w-[238px] text-[16px] font-light leading-4 text-[rgba(32,32,32,0.6)]">{body}</p>
        <p className="sr-only">{`Card ${slide + 1} of ${INTRO_SLIDES.length}`}</p>
      </div>
    </div>
  );
}

/**
 * Figma 5371:3746: "You're all set, @name!"; the 100px disc 58px under the
 * subtitle; 51px lower a white card at radius 12, 24px in — the stage in 16px
 * Medium with its level on a brand-tint pill (10px Regular orange, radius 8),
 * 16px over the line in 12px Light on 18px lines, 12px over an 8px track at
 * radius 12, and 12px under it the count in 10px Regular at 40%.
 */
function StepDone({ user, username }: { user: OnboardingUser; username: string }) {
  const target = 1;
  const progress = Math.min(user.verifiedReviewCount / target, 1) * 100;

  return (
    <div className="flex flex-col lg:mx-auto lg:w-full lg:max-w-[24rem]">
      <h1 className={TITLE}>{`You’re all set, @${username}!`}</h1>
      <p className={SUBTITLE}>We know you&rsquo;ll do great things</p>

      <span
        aria-hidden="true"
        className="mx-auto mt-[58px] grid h-[100px] w-[100px] place-items-center rounded-full bg-[var(--base-gray-200)] text-[var(--text-primary)]"
      >
        <Confetti size={48} weight="light" />
      </span>

      <div className="mt-[51px] rounded-[12px] bg-white p-6 lg:bg-[var(--surface-app)]">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-[16px] font-medium leading-none text-[var(--text-primary)]">{user.trustLevelName}</h2>
          <span className="inline-flex h-[23px] shrink-0 items-start rounded-[8px] bg-[rgba(239,88,33,0.08)] px-2 pt-1 text-[10px] leading-none text-[var(--accent-primary)]">
            {`Level ${user.trustStage}`}
          </span>
        </div>
        <p className="mt-4 text-[12px] font-light leading-[18px] text-[var(--text-primary)]">
          {/* A first verified review makes a Verified Buyer (stage 2) — which is
              what unlocks earning. Contributor (stage 1) is any first review. */}
          {`Post your first verified review to become a ${trustLevelName(2)} and unlock earnings.`}
        </p>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={target}
          aria-valuenow={user.verifiedReviewCount}
          className="mt-3 h-2 w-full overflow-hidden rounded-[12px] bg-[rgba(240,238,233,0.91)]"
        >
          <span
            className="block h-full rounded-[12px] bg-[var(--accent-primary)]"
            style={{ width: progress > 0 ? `${progress}%` : 15 }}
          />
        </div>
        <p className="mt-3 text-[10px] leading-none text-[rgba(32,32,32,0.4)]">
          {`${user.verifiedReviewCount} of ${target} verified review to become a ${trustLevelName(2)}`}
        </p>
      </div>
    </div>
  );
}

export default OnboardingWizard;
