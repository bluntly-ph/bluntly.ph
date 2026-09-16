"use client";

import Link from "next/link";
import { useActionState, useRef, useState } from "react";
import { Camera, Check, Trash } from "@phosphor-icons/react/dist/ssr";

import { saveProfile, type ProfileState } from "@/app/actions/profile";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { INTERESTS } from "@/lib/interests";

/**
 * Editing an existing profile (BUG-035).
 *
 * QA: "Clicking Edit on /profile routes into the full 4-step onboarding flow…
 * Step 2 does not show the user's previously selected interests… After Step 3,
 * Continue shows 'Setting up…' for 1–2 seconds before automatically
 * redirecting to home."
 *
 * The root problem was not any of those three details. It was that Edit and
 * onboarding were the same screen, and they are not the same job: onboarding
 * introduces the site to someone who has not seen it, and an edit changes one
 * field for someone who has been here for months. Pre-filling the wizard would
 * have fixed the symptom and left a returning member walking through "Search or
 * Ask", "Shop confidently" and "Say it bluntly" to change their display name.
 *
 * So this is one form, everything on it at once, every value already filled in,
 * and Save returns to `/profile` where the change is visible.
 *
 * WHAT IS EDITABLE is what the account actually stores: handle, display name,
 * photo, interests. A bio is not — `users` has no such column — and inventing
 * an input that writes nowhere would be a worse bug than the one being fixed.
 * That absence is recorded against BUG-036 rather than papered over here.
 */
export function EditProfileForm({
  username,
  displayName,
  avatarUrl,
  interests: initialInterests,
}: {
  username: string;
  displayName: string;
  avatarUrl: string | null;
  interests: string[];
}) {
  const [state, action, pending] = useActionState<ProfileState, FormData>(saveProfile, {});
  const [interests, setInterests] = useState<string[]>(initialInterests);
  const [preview, setPreview] = useState<string | null>(avatarUrl);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  function toggle(slug: string) {
    setInterests((current) =>
      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
    );
  }

  function onPickFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setRemoveAvatar(false);
    // Revoked on the next pick rather than on unmount: the object URL has to
    // outlive this handler, and leaking one per pick is not worth an effect.
    setPreview((old) => {
      if (old?.startsWith("blob:")) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });
  }

  function clearPhoto() {
    if (fileRef.current) fileRef.current.value = "";
    setPreview((old) => {
      if (old?.startsWith("blob:")) URL.revokeObjectURL(old);
      return null;
    });
    setRemoveAvatar(true);
  }

  const initial = (displayName || username || "?").slice(0, 1).toUpperCase();

  return (
    <form action={action} className="flex flex-col gap-8">
      <input type="hidden" name="interests" value={interests.join(",")} />
      <input type="hidden" name="remove_avatar" value={removeAvatar ? "1" : ""} />

      {/* --- photo ----------------------------------------------------- */}
      <section>
        <h2 className="text-[14px] font-medium leading-none text-[var(--text-primary)]">
          Photo
        </h2>
        <div className="mt-4 flex items-center gap-4">
          <span className="relative grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full bg-[var(--base-gray-200)] text-[28px] font-semibold text-white">
            {preview ? (
              // Not next/image: a blob: URL from the file picker has no loader
              // and no known dimensions, and the point of this element is to
              // show the photo the reader just chose.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="" className="h-full w-full object-cover" />
            ) : (
              <span aria-hidden="true">{initial}</span>
            )}
          </span>

          <div className="flex flex-wrap gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[13px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] hover:bg-[var(--line-hairline-10)] focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--accent-primary)]">
              <Camera size={16} aria-hidden="true" />
              {preview ? "Change photo" : "Add a photo"}
              <input
                ref={fileRef}
                type="file"
                name="avatar"
                accept="image/png,image/jpeg,image/webp"
                onChange={onPickFile}
                className="sr-only"
              />
            </label>
            {preview ? (
              <button
                type="button"
                onClick={clearPhoto}
                className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--accent-danger)]"
              >
                <Trash size={16} aria-hidden="true" /> Remove
              </button>
            ) : null}
          </div>
        </div>
      </section>

      {/* --- identity --------------------------------------------------- */}
      <section className="flex flex-col gap-5">
        <TextField
          label="Display name"
          name="display_name"
          defaultValue={displayName}
          maxLength={120}
          hint="The name shown on your reviews. Your handle stays the same unless you change it below."
          error={state.fieldErrors?.display_name}
        />
        <TextField
          label="Handle"
          name="username"
          defaultValue={username}
          minLength={3}
          maxLength={32}
          pattern="[a-z0-9_]+"
          adornment="@"
          hint="Lowercase letters, numbers and underscores. This is your profile address."
          error={state.fieldErrors?.username}
        />
      </section>

      {/* --- interests --------------------------------------------------- */}
      <section>
        <h2 className="text-[14px] font-medium leading-none text-[var(--text-primary)]">
          Shops for
        </h2>
        <p className="mt-1 text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          What you buy, so the feed leads with it. Your current picks are already
          selected — change as many as you like, or none.
        </p>
        <ul className="mt-4 flex flex-wrap gap-2">
          {INTERESTS.map((interest) => {
            const picked = interests.includes(interest.slug);
            return (
              <li key={interest.slug}>
                <button
                  type="button"
                  onClick={() => toggle(interest.slug)}
                  aria-pressed={picked}
                  className={`inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[13px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] ${
                    picked
                      ? "bg-[var(--accent-primary)] text-white"
                      : "text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] hover:bg-[var(--line-hairline-10)]"
                  }`}
                >
                  {picked ? <Check size={14} weight="bold" aria-hidden="true" /> : null}
                  {interest.label}
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {state.error ? (
        <p role="alert" className="text-[13px] text-[var(--accent-danger)]">
          {state.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Save changes"}
        </Button>
        <Link
          href="/profile"
          className="text-[13px] text-[var(--text-secondary)] underline-offset-2 hover:text-[var(--text-primary)] hover:underline"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}

export default EditProfileForm;
