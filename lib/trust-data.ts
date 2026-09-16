import "server-only";

import { apiFetch } from "./api/client";

/**
 * The read side of a member's trust profile (`GET /users/{id}/trust`).
 *
 * Separate from `lib/trust.ts`, which is pure formatting and therefore
 * importable from client components. This module fetches, so it is server-only;
 * keeping the two apart is what lets a client component still render a badge.
 */

export type TrustProgress = {
  next_stage: number;
  next_level_name: string;
  reviews_have: number;
  reviews_needed: number;
};

export type TrustProfile = {
  id: string;
  trust_stage: number;
  trust_level_name: string;
  reputation_score: string;
  verified_review_count: number;
  helpfulness_ratio: string;
  badges: { badge_id: string; name: string; awarded_at: string }[];
  /** null at the top of the ladder — nothing further to progress towards. */
  progress: TrustProgress | null;
};

/**
 * A member's trust profile, or null if the API could not be reached.
 *
 * null rather than a zeroed object: "we could not load your progress" and "you
 * have made no progress" are different things to tell someone about their own
 * standing, and only one of them is true.
 */
export async function getTrustProfile(userId: string): Promise<TrustProfile | null> {
  try {
    return await apiFetch<TrustProfile>(`/api/v1/users/${userId}/trust`, {
      revalidate: 60,
    });
  } catch {
    return null;
  }
}
