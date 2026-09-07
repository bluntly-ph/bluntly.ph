/**
 * Presentation logic for the console's Answers tab (frame 6532:278).
 *
 * Same shape and same rule as `review-queue-model.ts`: plain functions,
 * structural input types, no imports, and no number printed that the Q&A
 * schema does not carry.
 *
 * What the frame draws and what `backend/app/schemas/qa.py` serves diverge in
 * two places, both handled here rather than papered over:
 *
 *  - the asker/responder cards draw Age, Trust Score, Total Reviews and
 *    Verified Reviews, but `QAAuthor` carries only identity, trust stage,
 *    trust level name and reputation score;
 *  - the answer card draws a three-photo grid, and no answers table, schema,
 *    endpoint or storage bucket holds an answer photo.
 */

export type QaAuthor = {
  id: string;
  username: string | null;
  display_name: string | null;
  trust_stage: number;
  trust_level_name: string | null;
  reputation_score: string | null;
};

export type QaAnswer = {
  id: string;
  body: string;
  is_best_answer: boolean;
  is_first_responder: boolean;
  created_at: string;
  responder: QaAuthor | null;
};

export type QaQuestion = {
  id: string;
  product_name: string | null;
  body: string;
  answer_count: number;
  created_at: string;
  asker: QaAuthor | null;
};

export type QaQuestionDetail = QaQuestion & {
  best_answer_id: string | null;
  answers: QaAnswer[];
};

export type Stat =
  | { label: string; available: true; value: string }
  | { label: string; available: false; value: null; reason: string };

export type Photos =
  | { available: true; urls: string[] }
  | { available: false; reason: string };

const available = (label: string, value: string): Stat => ({
  label,
  available: true,
  value,
});

const unavailable = (label: string, reason: string): Stat => ({
  label,
  available: false,
  value: null,
  reason,
});

/* ------------------------------------------------------------ answer choice */

/**
 * Which answer the detail pane shows.
 *
 * With nothing selected the accepted answer wins over the earliest one: that
 * is the answer the asker endorsed, and it is what a moderator opened the
 * question to look at. A selection that no longer exists — the id left behind
 * by the previously selected question — falls back the same way.
 */
export function selectAnswer(
  detail: QaQuestionDetail,
  selectedId: string | null,
): QaAnswer | null {
  if (detail.answers.length === 0) return null;

  const chosen = selectedId
    ? detail.answers.find((a) => a.id === selectedId)
    : undefined;
  if (chosen) return chosen;

  const best =
    detail.answers.find((a) => a.is_best_answer) ??
    (detail.best_answer_id
      ? detail.answers.find((a) => a.id === detail.best_answer_id)
      : undefined);

  return best ?? detail.answers[0];
}

/** The chip that selects one answer. */
export function answerTabLabel(answer: QaAnswer, index: number): string {
  const name =
    answer.responder?.display_name?.trim() ||
    answer.responder?.username?.trim() ||
    `Answer ${index + 1}`;
  return answer.is_best_answer ? `${name} · Best` : name;
}

/* ------------------------------------------------------------ author stats */

const NO_QA_AGE =
  "QAAuthor carries no created_at, so a Q&A card cannot show account age. " +
  "The value exists on the user record but is not serialized here.";

const NO_QA_REVIEW_COUNT =
  "QAAuthor carries no review counts. Showing this would need the Q&A author " +
  "schema widened, not a number borrowed from another surface.";

/**
 * The four stats beside a Q&A participant's name.
 *
 * Only the trust score has a source. It is rendered the same way the public
 * question page already renders it, so the two surfaces agree.
 */
export function qaAuthorStats(author: QaAuthor | null): Stat[] {
  const score = author?.reputation_score;
  const numeric = score === null || score === undefined || score === "" ? null : Number(score);

  return [
    unavailable("Age", NO_QA_AGE),
    numeric !== null && Number.isFinite(numeric)
      ? available("Trust Score", String(Math.round(numeric)))
      : unavailable("Trust Score", "This account no longer exists."),
    unavailable("Total Reviews", NO_QA_REVIEW_COUNT),
    unavailable("Verified Reviews", NO_QA_REVIEW_COUNT),
  ];
}

/* ----------------------------------------------------------------- photos */

const NO_ANSWER_PHOTOS =
  "Answers hold text only. No answers column, schema field, endpoint or " +
  "storage bucket in this build stores an answer photo.";

/**
 * The frame's three-photo grid under the answer.
 *
 * Unavailable rather than an empty gallery: an empty grid reads as "this
 * responder attached nothing", which is a claim about the responder rather
 * than about the product.
 */
export function answerPhotos(): Photos {
  return { available: false, reason: NO_ANSWER_PHOTOS };
}

/* ---------------------------------------------------------- question list */

export function questionRows<T extends QaQuestion>(rows: T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...rows];

  return rows.filter(
    (q) =>
      q.body.toLowerCase().includes(needle) ||
      (q.product_name ?? "").toLowerCase().includes(needle) ||
      (q.asker?.display_name ?? "").toLowerCase().includes(needle) ||
      (q.asker?.username ?? "").toLowerCase().includes(needle),
  );
}
