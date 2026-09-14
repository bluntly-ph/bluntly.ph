/**
 * What a question is about, and who an answer is from (FR-4, FR-5).
 *
 * A question is about a product or a store (migration 0045), never both. An
 * answer is shown as the store only when the API marked it as the claimed
 * owner's (`is_seller_answer`). Every Q&A surface goes through these two
 * functions, so a store question is never labelled "Unnamed product" and a
 * buyer's answer can never wear the store's name.
 */

export type QuestionSubjectFields = {
  product_id: string | null;
  product_name: string | null;
  seller_id?: string | null;
  seller_name?: string | null;
};

export type QuestionSubject = {
  kind: "product" | "seller";
  label: string;
  /** The store page for a store question; products have no page of their own. */
  href: string | null;
};

export function questionSubject(q: QuestionSubjectFields): QuestionSubject {
  if (q.seller_id) {
    return { kind: "seller", label: q.seller_name ?? "Unnamed store", href: `/sellers/${q.seller_id}` };
  }
  return { kind: "product", label: q.product_name ?? "Unnamed product", href: null };
}

export type AnswerBylineFields = {
  is_seller_answer?: boolean;
  seller_name?: string | null;
  responder: { username: string | null; display_name: string | null } | null;
};

export function answerByline(a: AnswerBylineFields): { name: string; seller: boolean } {
  if (a.is_seller_answer && a.seller_name) return { name: a.seller_name, seller: true };
  return {
    name: a.responder?.display_name ?? a.responder?.username ?? "Former member",
    seller: false,
  };
}
