import "server-only";

import { apiFetch } from "./api/client";

/**
 * Read side for the review comment thread (BUG-014).
 *
 * Fetched server-side so the thread is in the first HTML payload rather than
 * appearing a beat after hydration. Mutations go the other way — through the BFF
 * from the client component, so the session token stays on the server.
 */

export type CommentAuthor = {
  id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  trust_stage: number | null;
  trust_level_name: string | null;
};

export type Comment = {
  id: string;
  review_id: string;
  parent_id: string | null;
  body: string;
  helpful_votes: number;
  unhelpful_votes: number;
  is_removed: boolean;
  created_at: string;
  author: CommentAuthor | null;
  my_vote: "up" | "down" | null;
  replies: Comment[];
};

/**
 * The thread for a review, oldest first, replies nested one level.
 *
 * A failure returns an empty thread rather than throwing: a comments outage
 * should cost the reader the discussion, not the review they came to read.
 */
export async function getComments(
  reviewId: string,
  token?: string | null,
): Promise<Comment[]> {
  try {
    return await apiFetch<Comment[]>(`/api/v1/reviews/${reviewId}/comments`, {
      token,
      // Only takes effect for signed-out readers: apiFetch drops `revalidate`
      // whenever a token is present, so a signed-in thread — which carries that
      // viewer's own `my_vote` — is never shared. Signed-out responses have
      // `my_vote: null` throughout and are identical for everyone.
      revalidate: 30,
    });
  } catch {
    return [];
  }
}
