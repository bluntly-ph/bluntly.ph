"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { getSessionToken } from "@/lib/session";

export type ProfileState = {
  error?: string;
  fieldErrors?: Record<string, string>;
  ok?: boolean;
};

function toState(error: unknown): ProfileState {
  if (error instanceof ApiError) {
    const fieldErrors = error.fieldErrors();
    return {
      error: error.problem.detail,
      fieldErrors: Object.keys(fieldErrors).length ? fieldErrors : undefined,
    };
  }
  throw error;
}

/**
 * Onboarding step 1 — choose a handle and optionally a photo.
 *
 * OTP signup derives a handle from the email address, so the user always has a
 * valid one; this is where they replace it with something they chose.
 */
export async function completeOnboarding(
  _prev: ProfileState,
  formData: FormData,
): Promise<ProfileState> {
  const token = await getSessionToken();
  if (!token) redirect("/login");

  const username = String(formData.get("username") ?? "")
    .trim()
    .toLowerCase();
  const displayName = String(formData.get("display_name") ?? "").trim();
  // The wizard carries the picks as a comma-joined hidden field, since a
  // multi-select of custom cards has no native form control.
  const interests = String(formData.get("interests") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  try {
    await apiFetch("/api/v1/users/me", {
      method: "PATCH",
      token,
      json: {
        ...(username ? { username } : {}),
        ...(displayName ? { display_name: displayName } : {}),
        ...(interests.length ? { interests } : {}),
      },
    });

    const avatar = formData.get("avatar");
    // An empty file input still submits a zero-byte File; skip it.
    if (avatar instanceof File && avatar.size > 0) {
      const body = new FormData();
      body.append("file", avatar);
      await apiFetch("/api/v1/users/me/avatar", {
        method: "POST",
        token,
        body,
      });
    }
  } catch (error) {
    return toState(error);
  }

  revalidatePath("/", "layout");
  redirect("/");
}

/**
 * Save an edit to an existing profile (BUG-035).
 *
 * Distinct from `completeOnboarding`, which it deliberately does not reuse,
 * because the two are different jobs that only look alike:
 *
 *   * onboarding redirects to `/`, because the point is to start exploring.
 *     An edit returns to `/profile`, because the point is to see the change.
 *   * onboarding sends interests only when there are some — a first-time user
 *     cannot un-pick something they never picked. An edit must be able to clear
 *     a field, so the interests array is always sent, empty included.
 *
 * The avatar is a second request because it is a second endpoint: `PATCH
 * /users/me` takes JSON and the photo is multipart. A failure there is
 * reported rather than swallowed — an edit that says it saved and did not is
 * exactly the complaint that produced BUG-028.
 */
export async function saveProfile(
  _prev: ProfileState,
  formData: FormData,
): Promise<ProfileState> {
  const token = await getSessionToken();
  if (!token) redirect("/login");

  const username = String(formData.get("username") ?? "").trim().toLowerCase();
  const displayName = String(formData.get("display_name") ?? "").trim();
  const interests = String(formData.get("interests") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  try {
    await apiFetch("/api/v1/users/me", {
      method: "PATCH",
      token,
      json: {
        ...(username ? { username } : {}),
        display_name: displayName,
        interests,
      },
    });

    const avatar = formData.get("avatar");
    if (avatar instanceof File && avatar.size > 0) {
      const body = new FormData();
      body.append("file", avatar);
      await apiFetch("/api/v1/users/me/avatar", { method: "POST", token, body });
    } else if (String(formData.get("remove_avatar") ?? "") === "1") {
      await apiFetch("/api/v1/users/me/avatar", { method: "DELETE", token });
    }
  } catch (error) {
    return toState(error);
  }

  // The whole layout, not just /profile: the handle and the photo are in the
  // header on every page, and BUG-028 was precisely a change that looked saved
  // until the next request served a cached copy of the old one.
  revalidatePath("/", "layout");
  redirect("/profile");
}
