import "server-only";

import { apiFetch } from "./api/client";

/** A community review request (GET /api/v1/requests). */
export type RequestItem = {
  id: string;
  title: string;
  details: string;
  source_url: string | null;
  upvote_count: number;
  /**
   * Whether the requesting viewer has up-voted this (BUG-026). Only populated
   * when the call carries a token; false for anonymous reads.
   */
  my_upvote: boolean;
  status: string;
  created_at: string;
};

/**
 * Open requests, newest or most-wanted.
 *
 * Readable without a token; pass the viewer's to get `my_upvote` filled in, so
 * the board renders their existing up-votes as pressed instead of resetting on
 * every load.
 */
export async function getRequests(
  sort: "demand" | "newest" = "demand",
  token?: string | null,
): Promise<RequestItem[]> {
  try {
    return await apiFetch<RequestItem[]>(
      `/api/v1/requests?status=open&sort=${sort}&limit=30`,
      { token: token ?? undefined },
    );
  } catch {
    return [];
  }
}
