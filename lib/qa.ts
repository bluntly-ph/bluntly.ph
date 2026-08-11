import "server-only";

import { apiFetch } from "./api/client";

export type QAAuthor = {
  id: string;
  username: string | null;
  display_name: string | null;
  trust_stage: number;
  trust_level_name: string | null;
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
export async function getQuestions(productId?: string): Promise<Question[]> {
  try {
    const qs = productId ? `?product_id=${productId}&limit=30` : "?limit=30";
    return await apiFetch<Question[]>(`/api/v1/questions${qs}`, { revalidate: 60 });
  } catch {
    return [];
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
