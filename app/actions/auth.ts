"use server";

import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { createSession, destroySession, setThemePreference } from "@/lib/session";

/**
 * Auth Server Actions.
 *
 * These run on the server, so credentials never transit client JavaScript and
 * the resulting token goes straight into an httpOnly cookie.
 *
 * Both /auth/login and /auth/otp/verify return the same TokenResponse, so
 * `establish` is the single place a session is created.
 */

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: { id: string; email: string; username: string | null };
};

export type FormState = {
  error?: string;
  /** Keyed by field name, from a 422's `errors[]`. */
  fieldErrors?: Record<string, string>;
  /** Set by requestOtp so the UI can advance to the code step. */
  emailSent?: string;
  ok?: boolean;
};

/** A safe internal destination — never redirect to an attacker-supplied host. */
function safeNext(raw: FormDataEntryValue | null): string {
  const value = typeof raw === "string" ? raw : "";
  return value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function toFormState(error: unknown): FormState {
  if (error instanceof ApiError) {
    const fieldErrors = error.fieldErrors();
    return {
      error: error.problem.detail,
      fieldErrors: Object.keys(fieldErrors).length ? fieldErrors : undefined,
    };
  }
  throw error;
}

async function establish(token: TokenResponse): Promise<void> {
  await createSession(token.access_token, token.expires_in);
}

export async function login(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const next = safeNext(formData.get("next"));
  try {
    // OAuth2 password flow: a FORM post whose `username` field is the email.
    const token = await apiFetch<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      form: {
        username: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
      },
    });
    await establish(token);
  } catch (error) {
    return toFormState(error);
  }
  redirect(next);
}

export async function register(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const username = String(formData.get("username") ?? "").trim();
  try {
    const token = await apiFetch<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      json: {
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
        ...(username ? { username: username.toLowerCase() } : {}),
      },
    });
    await establish(token);
  } catch (error) {
    return toFormState(error);
  }
  redirect("/");
}

export async function requestOtp(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();
  const purpose = formData.get("purpose") === "login" ? "login" : "signup";
  try {
    await apiFetch<{ status: string }>("/api/v1/auth/otp/request", {
      method: "POST",
      json: { email, purpose },
    });
  } catch (error) {
    return toFormState(error);
  }
  // Always advances, even for an unknown address: the backend deliberately
  // returns 202 either way so this cannot be used to enumerate accounts.
  return { emailSent: email, ok: true };
}

export async function verifyOtp(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  try {
    const token = await apiFetch<TokenResponse>("/api/v1/auth/otp/verify", {
      method: "POST",
      json: {
        email: String(formData.get("email") ?? ""),
        code: String(formData.get("code") ?? ""),
      },
    });
    await establish(token);
  } catch (error) {
    return toFormState(error);
  }
  redirect("/onboarding");
}

export async function logout(): Promise<void> {
  await destroySession();
  redirect("/");
}

export async function setTheme(theme: "light" | "dark"): Promise<void> {
  await setThemePreference(theme);
}
