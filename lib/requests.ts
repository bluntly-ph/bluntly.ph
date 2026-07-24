import "server-only";

import { apiFetch } from "./api/client";

/** A community review request / bounty (GET /api/v1/requests). */
export type RequestItem = {
  id: string;
  title: string;
  details: string;
  source_url: string | null;
  bounty: number;
  effective_reward: number;
  upvote_count: number;
  status: string;
  created_at: string;
};

/** Open requests, newest or by reward. Public — no token needed. */
export async function getRequests(
  sort: "reward" | "newest" = "reward",
): Promise<RequestItem[]> {
  try {
    return await apiFetch<RequestItem[]>(
      `/api/v1/requests?status=open&sort=${sort}&limit=30`,
    );
  } catch {
    return [];
  }
}
