# Frontend integration guide (M3 slice 13)

Everything the Next.js app needs to talk to this backend. No frontend pages are
built yet (owner decision — the frontend is a separate track); this is the
contract they build against.

- **Live spec:** `docs/openapi.json` (52 paths, 62 operations, all tagged).
  Browse it at `‹API›/docs` when `ENABLE_DOCS=true`.
- **Types:** `lib/api-types.d.ts`, generated. Regenerate after any API change:
  ```bash
  npm run gen:api        # openapi-typescript docs/openapi.json -o lib/api-types.d.ts
  ```
  Re-export the spec first if the backend changed:
  `cd backend && python -m scripts.export_openapi`.

## 1. Environment

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000        # the backend origin
NEXT_PUBLIC_SUPABASE_URL=...                     # existing
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=...         # existing; safe client-side
```

The backend must allow your origin: set `CORS_ORIGINS` (comma-separated) in the
**backend** env — e.g. `CORS_ORIGINS=http://localhost:3000,https://bluntly.ph`.
It must never contain `*` in production (the startup guard refuses to boot).

## 2. Auth

App-issued **HS256 JWT**, sent as `Authorization: Bearer <token>`. Supabase Auth
is NOT used for login (ADR-010/011).

```ts
// register -> {access_token, expires_in, user}
POST /api/v1/auth/register   {email, password, display_name?, username?}
// login is an OAuth2 password FORM post, not JSON:
POST /api/v1/auth/login      Content-Type: application/x-www-form-urlencoded
                             username=<email>&password=<password>
GET  /api/v1/auth/me         -> the current user
```

**Passwordless (email OTP).** A second, equal path — one account can use either.

```ts
POST /api/v1/auth/otp/request  {email, purpose:"signup"|"login"}  -> 202
POST /api/v1/auth/otp/verify   {email, code}                      -> TokenResponse
```

- `otp/request` **always returns 202**, registered or not. It is deliberately not
  an enumeration oracle, so never render "no account with that email" from it.
  A signup request for an existing address quietly becomes a login code.
- `otp/verify` returns the **identical `TokenResponse`** as `/auth/login`, so
  session creation is one code path regardless of how the user authenticated.
- Codes are 6 digits, expire in 10 minutes, are single-use, and requesting a new
  one invalidates the previous. After 5 wrong attempts the code is dead and the
  user must request another.

**Identity fields.** `username` is the unique, URL-safe `@handle` (3–32 chars,
`^[a-z0-9_]+$`, case-insensitively unique). `display_name` is the free-text
label and is **not** unique. Both are on `UserOut`, alongside `avatar_url`.

```ts
POST   /api/v1/users/me/avatar   multipart/form-data, field name `file` -> UserOut
DELETE /api/v1/users/me/avatar                                          -> 204
```
PNG/JPEG/WebP only, 5 MB max. The type is sniffed server-side from magic bytes,
so a mislabelled `Content-Type` is rejected regardless of what the browser sends.

- Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440). On `401` with
  `code: "token_expired"`, clear the session and send the user to login — there is
  no refresh token.
- Roles are read from the DB per request, so a promotion takes effect immediately;
  never trust a role baked into a stale token.

## 3. The error contract — one shape everywhere

Every error is `application/problem+json` (RFC 9457). **Branch on `code`, never on
the message.**

```ts
type Problem = {
  type: string; title: string; status: number;
  detail: string; instance: string; code: string;
  [extra: string]: unknown;   // e.g. errors[], reasons[], retry_after_seconds
};
```

Codes worth handling explicitly:

| code | status | What the UI should do |
|---|---|---|
| `validation_error` | 422 | Field errors are in `errors[]` (`loc`, `msg`). |
| `unauthorized` / `token_expired` | 401 | Send to login. |
| `forbidden` / `role_forbidden` | 403 | Hide the control; don't offer the action. |
| `rate_limited` | 429 | Back off `retry_after_seconds`. |
| `cannot_vote_own_review` | 409 | Disable voting on your own review. |
| `insufficient_tokens` | 409 | Show the balance and the shortfall. |
| `request_invalid` | 422 | Show `reasons[]` from AI screening verbatim. |
| `review_not_published` | 409 | Explain the review is still awaiting a moderator. |
| `seller_review_exists` | 409 | You already reviewed this seller. |
| `otp_invalid` | 409 | Clear the input and let them retry. |
| `otp_expired` | 409 | Offer "send a new code". |
| `otp_attempts_exceeded` | 429 | The code is dead; force a new request. |
| `username_taken` | 409 | Mark the field; suggest an alternative. |
| `unsupported_media_type` | 415 | Explain PNG/JPEG/WebP only. |
| `file_too_large` | 413 | Explain the 5 MB cap. |
| `buyout_already_pending` | 409 | Refresh the contract; an offer exists. |

## 4. Page → endpoint map

### Review listing
`GET /api/v1/reviews?sort=wilson|newest&product_id=&limit=` — **`newest` is the
default; use `sort=wilson`** for "most helpful", which is the time-decayed Wilson
ranking (a fresh 1-vote review must not outrank a proven one).

### Product page
`GET /api/v1/products/{id}` → includes `trust_score` and a computed `low_trust`
flag. `GET /api/v1/products?include_low_trust=true` shows everything; by default
low-trust products are filtered from the listing **only when thresholds are
switched on** (they ship off). Show the `low_trust` badge rather than hiding.

### Submitting a review — the publication gate
`POST /api/v1/reviews` returns `published_at: null` and
`earn_eligible_status: "pending"`. **This is not an error.** The review is queued
for a moderator; the author can see and edit their own draft
(`GET /api/v1/reviews` while authenticated includes your drafts). Render an
"awaiting review" state, not a failure.

A photo at submission ⇒ `verification_status: "verified"`.

### Affiliate links — never render the raw URL
The raw affiliate URL **is not exposed by the API, ever**. `ReviewOut` carries
`referral_redirect_url` (`/r/{id}`) once the review is published *and* monetized;
link the buy button to that. It records attribution and 302s onward.

### Voting
`POST /api/v1/reviews/{id}/vote {vote:"up"|"down"}` (re-POST to change),
`DELETE` to remove. Rate-limited (`VOTE_RATE_LIMIT_MAX`/60s → `429`). Published
reviews only; self-votes are `409`.

### Trust profile
`GET /api/v1/users/{id}/trust` (public) → `trust_stage` (0–5),
`trust_level_name`, `reputation_score`, `verified_review_count`,
`helpfulness_ratio`, `badges[]`.

### Sellers
`GET /api/v1/sellers/{id}` (profile + per-dimension averages + `low_trust`),
`GET|POST /api/v1/sellers/{id}/reviews`. Seller reviews publish immediately (no
moderator gate) — one per reviewer per seller.

### Moderator queue (one card per review)
`GET /api/v1/admin/review-queue?limit=&offset=` → `pending[]` +
`edited_since_monetized[]`. Each card carries the review, product, author,
`suggested_platform`, advisory `signals` (velocity / collusion /
duplicate_content — **advisory only, never auto-blocking; show, don't act**), and
**`suggested_sub_id`**.

> **The sub-ID is load-bearing.** The moderator must paste `suggested_sub_id`
> into the affiliate dashboard's sub-ID field when generating the link, then send
> it back with `POST /api/v1/admin/reviews/{id}/referral-link {url, platform,
> sub_id}`. It is the only identifier that comes back in the monthly report, so
> without it the commission can never be attributed. If the response has
> `sub_id_in_url: false`, warn the moderator. See `AFFILIATE_REPORT_FORMATS.md`.

Actions: `POST …/publish` (no link; ≤2★ → Honesty Fund), `POST …/reject`,
`POST …/unpublish`, `DELETE …/referral-link`, `GET …/referral-links` (history).

### Tokens
`GET /api/v1/tokens/balance`, `GET /api/v1/tokens/transactions?limit=&offset=`
(own only, newest first, append-only ledger with a `balance_after` chain).
Moderator: `POST /api/v1/admin/users/{id}/tokens {amount, note}` (sign picks
grant vs deduct).

### Request board
`GET /api/v1/requests?status=open&sort=reward|newest` — show `effective_reward`
(= bounty + capped up-vote top-up), not `bounty`. `POST /api/v1/requests`
escrows the bounty (`409 insufficient_tokens` if short; `422 request_invalid`
with `reasons[]` from AI screening). `POST|DELETE …/upvote`,
`POST …/fulfill {review_id}` (your own **published** review),
`DELETE …/{id}` to cancel and refund.

### Contracts
`GET /api/v1/contracts` (own), `PATCH …/{id}/auto-renew {auto_renew}`,
`POST …/{id}/buyout/accept|reject`. Surface `expires_at`, `auto_renew`, and any
pending `buyout_offer_amount` prominently — accepting ends the revenue share.

### Payouts
`PATCH /api/v1/auth/me/payout-account {payout_account}` — **without this the user
is skipped by the scheduler**; prompt for it once the wallet nears
`PAYOUT_MIN_PHP` (300). `GET /api/v1/payouts` (own). Statuses:
`scheduled → processing → paid`, or `failed`/`cancelled` (both refund the
wallet). The wallet is debited at *scheduled*, so a pending payout is money
already reserved — say so in the UI.

## 5. Conventions

- All money is a **string-encoded decimal** (`"30.00"`) — parse with a decimal
  library, never `Number`, for arithmetic.
- All ids are UUID strings; timestamps are ISO-8601 UTC.
- `limit` is capped at 100 on every list endpoint.
- Pagination on the moderator queue is `limit`/`offset`; the pending list is
  **oldest-first** (a work queue), everything else is newest-first.
