import "server-only";

import { apiFetch } from "./api/client";

export type QAAuthor = {
  id: string;
  username: string | null;
  display_name: string | null;
  trust_stage: number;
  trust_level_name: string | null;
  /** 0..100 (ADR-003); shown beside the level name. See lib/trust.ts. */
  reputation_score: string | null;
};

export type Answer = {
  id: string;
  body: string;
  is_best_answer: boolean;
  is_first_responder: boolean;
  helpful_votes: number;
  created_at: string;
  responder: QAAuthor | null;
};

export type Question = {
  id: string;
  product_id: string;
  product_name: string | null;
  body: string;
  directed_to: "buyers" | "seller";
  best_answer_id: string | null;
  answer_count: number;
  created_at: string;
  asker: QAAuthor | null;
};

export type QuestionDetail = Question & { answers: Answer[] };

/** Open community questions. Public — no token needed. */
export async function getQuestions(
  productId?: string,
  options: { q?: string; limit?: number } = {},
): Promise<Question[] | null> {
  try {
    const params = new URLSearchParams({ limit: String(options.limit ?? 30) });
    if (productId) params.set("product_id", productId);
    // Free text, for the Questions tab on /search. The API matches the question
    // wording and the product name; a blank string is not a query, so it is
    // omitted rather than sent as an empty filter.
    const needle = options.q?.trim();
    if (needle) params.set("q", needle);
    return await apiFetch<Question[]>(`/api/v1/questions?${params}`, {
      revalidate: 60,
    });
  } catch {
    // See lib/requests.ts: null distinguishes "unreachable" from "none".
    return null;
  }
}

export async function getQuestionDetail(id: string): Promise<QuestionDetail | null> {
  try {
    return await apiFetch<QuestionDetail>(`/api/v1/questions/${id}`, {
      revalidate: 60,
    });
  } catch {
    return null;
  }
}
