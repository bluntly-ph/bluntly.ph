import "server-only";

import { ApiError, type Problem } from "./errors";

/**
 * The single place the frontend talks to FastAPI.
 *
 * Server-only by construction: the access token lives in an httpOnly cookie and
 * is attached here, on the server, so it never reaches client JavaScript. Client
 * components go through the BFF route handler instead of importing this.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON body. Mutually exclusive with `form` and `body`. */
  json?: unknown;
  /** Sent as application/x-www-form-urlencoded — the login endpoint needs this. */
  form?: Record<string, string>;
  /** Raw body, for multipart uploads. */
  body?: BodyInit;
  token?: string | null;
  headers?: Record<string, string>;
  /** Defaults to "no-store": auth-shaped data must never be cached. */
  cache?: RequestCache;
  signal?: AbortSignal;
};

function buildInit(options: RequestOptions): RequestInit {
  const headers: Record<string, string> = { ...options.headers };
  let body: BodyInit | undefined;

  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(options.form).toString();
  } else if (options.body !== undefined) {
    // Let fetch set the multipart boundary itself.
    body = options.body;
  }

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  return {
    method: options.method ?? "GET",
    headers,
    body,
    cache: options.cache ?? "no-store",
    signal: options.signal,
  };
}

/** A transport failure still has to reach callers as an ApiError. */
function transportProblem(path: string, cause: unknown): Problem {
  return {
    type: "about:blank",
    title: "Backend unreachable",
    status: 503,
    detail:
      cause instanceof Error
        ? `Could not reach the API: ${cause.message}`
        : "Could not reach the API.",
    instance: path,
    code: "backend_unreachable",
  };
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, buildInit(options));
  } catch (cause) {
    throw new ApiError(transportProblem(path, cause));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson =
    contentType.includes("application/json") ||
    contentType.includes("application/problem+json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    // Every backend error is problem+json; anything else means we hit a proxy,
    // a crash page, or the wrong host. Normalise it so callers see one shape.
    const problem: Problem =
      isJson && payload && typeof payload === "object" && "code" in payload
        ? (payload as Problem)
        : {
            type: "about:blank",
            title: "Unexpected error",
            status: response.status,
            detail: typeof payload === "string" ? payload : response.statusText,
            instance: path,
            code: `http_${response.status}`,
          };
    throw new ApiError(problem);
  }

  return payload as T;
}
