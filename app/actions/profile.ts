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

  try {
    await apiFetch("/api/v1/users/me", {
      method: "PATCH",
      token,
      json: {
        ...(username ? { username } : {}),
        ...(displayName ? { display_name: displayName } : {}),
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
