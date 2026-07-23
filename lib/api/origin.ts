import "server-only";

/**
 * Where the FastAPI backend lives.
 *
 * Server-only. The browser never calls the API directly — Server Components and
 * Server Actions go through `lib/api/client.ts`, and client components go
 * through `/api/bff/[...path]`. So this must NOT be a `NEXT_PUBLIC_` variable:
 * that prefix inlines the value into client bundles, publishing the backend
 * origin to anyone who views source for no benefit.
 *
 * `NEXT_PUBLIC_API_URL` is still read as a fallback so existing local setups
 * keep working, but `API_URL` is what production should set.
 */
export const API_ORIGIN =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";
