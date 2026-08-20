/**
 * The RFC 9457 error contract.
 *
 * Every error the backend emits is `application/problem+json` with a stable
 * `code`. Branch on `code`, never on `detail` — the message is prose and will
 * change. See docs/FRONTEND_INTEGRATION.md §3.
 */

export type ProblemCode =
  | "validation_error"
  | "unauthorized"
  | "token_expired"
  | "invalid_credentials"
  | "account_not_found"
  | "account_suspended"
  | "forbidden"
  | "role_forbidden"
  | "rate_limited"
  | "not_found"
  | "email_taken"
  | "username_taken"
  | "otp_invalid"
  | "otp_expired"
  | "otp_attempts_exceeded"
  | "unsupported_media_type"
  | "file_too_large"
  | "cannot_vote_own_review"
  | "insufficient_tokens"
  | "request_invalid"
  | "review_not_published"
  | "seller_review_exists"
  | "buyout_already_pending";

/** A single field error from a 422. `loc` is the pydantic location path. */
export type FieldError = {
  loc: (string | number)[];
  msg: string;
  type?: string;
};

export type Problem = {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: string;
  /** Present on `validation_error`. */
  errors?: FieldError[];
  /** Present on `request_invalid` — show verbatim, it is AI screening output. */
  reasons?: string[];
  /** Present on `rate_limited` and `otp_attempts_exceeded`. */
  retry_after_seconds?: number;
  [extra: string]: unknown;
};

export class ApiError extends Error {
  readonly problem: Problem;
  readonly status: number;
  readonly code: string;

  constructor(problem: Problem) {
    super(problem.detail || problem.title);
    this.name = "ApiError";
    this.problem = problem;
    this.status = problem.status;
    this.code = problem.code;
  }

  /** True when the session is gone and the user must log in again. */
  get isAuthExpired(): boolean {
    return this.code === "unauthorized" || this.code === "token_expired";
  }

  /**
   * Field errors keyed by field name, ready to hand to a form.
   * Pydantic's `loc` is like ["body", "email"]; the field is the last segment.
   */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const err of this.problem.errors ?? []) {
      const field = err.loc[err.loc.length - 1];
      if (typeof field === "string" && !(field in out)) {
        out[field] = err.msg;
      }
    }
    return out;
  }
}
