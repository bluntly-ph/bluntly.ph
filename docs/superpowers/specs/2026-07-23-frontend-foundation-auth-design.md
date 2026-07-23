# Slice 1 — Auth: Backend Gaps & Frontend Foundation

**Date:** 2026-07-23
**Status:** Approved, ready for implementation planning
**Design source:** Figma `lso4Ri4hDaZxvCebhUqlY5` (bluntly.ph)
**Backend contract:** `docs/FRONTEND_INTEGRATION.md`, `docs/openapi.json`

## 1. Context

The backend is complete through M3: 52 paths, 62 operations, verified against
Supabase. The frontend is an untouched `create-next-app` scaffold — Next.js
16.2.10, React 19.2.4, Tailwind v4, TypeScript.

The Figma file holds roughly 130 frames across two pages:

- **Page 1 — mobile, 390px** (~110 frames): landing, 14 Login/Signup states,
  search variants for buyer/reviewer/seller, categories, bookmarks, recent
  reads, profile, reviewer dashboard, review page, seller page, question page,
  three multi-step wizards (Reviewer Step 1→7, Seller Review Step 1→3.3,
  Question Page Step 1→3), and sheets/modals. Also holds 4 desktop-width
  (1280px) Admin Page frames.
- **Page 2 — desktop, 1280px** (~20 frames): landing (logged-in and
  no-account), review, FAQs, other info, updates, three Alternatives views,
  categories, sign up, log in, request review, request board, learn more.

Too large for one specification. It is decomposed into sequential slices; this
document specifies **Slice 1 only**. Later slices each get their own spec →
plan → implementation cycle.

### Slice sequence

1. **Auth — backend gaps then frontend foundation** (this document).
2. Read path — landing, search, categories, review page.
3. Reviewer submission wizard.
4. Seller and question flows.
5. Profile and reviewer dashboard (wallet, payouts, contracts).
6. Request board.
7. Admin/moderator console.

Slice 1 runs in two phases: **Phase A (backend)** closes the gaps that make the
mobile design unbuildable, then **Phase B (frontend)** builds against a real,
complete API. No mocks, no rework.

## 2. Design/backend conflicts, and how each is resolved

Verified against code, not assumed.

| Design shows | Backend reality | Resolution |
|---|---|---|
| Mobile OTP: `Send code` | No OTP endpoint. `backend/app/api/v1/routes/auth.py` has only `POST /auth/register` and an OAuth2 password-form `POST /auth/login`. | **Build it** (Phase A). |
| "We'll **text** you a code" over an **Email address** field | n/a — the design contradicts itself | **Email OTP.** Copy corrected to "We'll email you a code". No phone column, no SMS vendor. |
| `@username`, unique handle | No `username` column. `backend/app/models/user.py:60` has `display_name String(120)`, nullable, **not unique**. | **Build it** (Phase A), with backfill. |
| Avatar upload | No user image field in `backend/app/models/` or `backend/app/schemas/`. `photo_url` exists only on `review`. | **Build it** (Phase A). First real Supabase Storage integration. |
| Desktop signup has a **password** field; mobile has OTP | n/a | **Both paths coexist.** One account can authenticate either way. |
| Mobile light theme, desktop dark theme | n/a | Both built, via mode-aware semantic tokens. |
| `bluntly` (mobile) vs `bluntly.ph` + checkmark (desktop) | n/a | Owner decision: `bluntly` wordmark everywhere. The checkmark mark is dropped — record in `docs/DEVIATIONS.md`. |

The Figma file defines **zero Figma variables** (`get_variable_defs` returns
`{}`). There is no token system to import; the token layer is authored by hand
from measured frame values.

---

# Phase A — Backend

## 3. Email OTP

### 3.1 Security constraint driving the design

`backend/app/core/rate_limit.py:53` **fails open** — on a Redis outage the
limiter logs and allows. That is a defensible choice for password login, but it
is unsafe for OTP: with Redis down, an attacker gets unlimited guesses at a
6-digit code.

Therefore **the verify-attempt limit lives in Postgres, on the OTP row**, and is
enforced transactionally. Redis is used only as the *send* throttle, where
failing open merely permits extra emails.

### 3.2 Schema — `email_otps` (migration `0015_email_otp.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | String(320), indexed | Not FK'd to `users` — signup OTPs precede the user row. |
| `code_hash` | String(255) | Argon2id, reusing `app.core.security`. **The plaintext code is never stored.** |
| `purpose` | Enum(`signup`,`login`) | |
| `attempts` | SmallInteger, default 0 | Verify attempts against this row. |
| `expires_at` | timestamptz | Issued + `OTP_TTL_SECONDS` (default 600). |
| `consumed_at` | timestamptz, nullable | Single-use. |
| `created_at` | timestamptz | |

Partial index on `(email, purpose)` where `consumed_at IS NULL`.

Codes are 6 digits from `secrets.randbelow`. Comparison is constant-time via the
Argon2 verifier.

### 3.3 Endpoints

```
POST /api/v1/auth/otp/request  {email, purpose}  -> 202 Accepted
POST /api/v1/auth/otp/verify   {email, code}     -> TokenResponse
```

- `otp/request` **always returns the same 202**, regardless of whether the
  address is registered. No user enumeration. Requesting a new code invalidates
  any outstanding unconsumed code for that `(email, purpose)`.
- `otp/verify` returns the identical `TokenResponse` shape as
  `POST /auth/login`, so the frontend session layer has one code path. On
  `purpose=signup` it creates the user; on `purpose=login` it requires one.
- Failure codes, following the existing RFC 9457 contract in
  `app/core/errors.py`: `otp_invalid` (409), `otp_expired` (409),
  `otp_attempts_exceeded` (429), `rate_limited` (429).

### 3.4 Limits

- **Send:** Redis bucket `otp_request` via the existing `auth_rate_limiter`.
  Fails open by design; the blast radius is extra email.
- **Verify:** `attempts` incremented in the same transaction as the check.
  At `OTP_MAX_ATTEMPTS` (default 5) the row is consumed and further attempts
  return `otp_attempts_exceeded`. **This is the authoritative limit** and does
  not depend on Redis.

### 3.5 Email delivery

`backend/app/adapters/email.py`, following the shape of `adapters/paypal.py`.

- Provider: **Resend** (HTTP API). Config: `RESEND_API_KEY`, `EMAIL_FROM`,
  `EMAIL_PROVIDER` (`resend` | `console`). A key is provisioned and
  `EMAIL_PROVIDER=resend` is set in the root `.env`.
- `console` provider logs the code instead of sending. **The test suite pins
  `EMAIL_PROVIDER=console`** — pytest must never make a network call to Resend
  or send real mail. It is also the fallback for offline development.
- **Sending-domain constraint.** `EMAIL_FROM` is currently
  `onboarding@resend.dev`, Resend's shared testing sender. It only delivers to
  the Resend account owner's own address. Until a domain is verified, OTP
  signup works end-to-end **only for that address** — every other recipient is
  rejected by Resend. Verifying `bluntly.ph` is a prerequisite for any real
  user testing, and is tracked in §13.
- The startup guard in `config.py` (which already refuses to boot on unsafe
  production config) is extended: `APP_ENV=production` with
  `EMAIL_PROVIDER=console` is a boot failure.

## 4. Username (migration `0016_username.py`)

Add `users.username`, `String(32)`, unique, indexed.

Three-step migration so it is safe and rerunnable:

1. Add the column nullable.
2. Backfill: slugify `display_name` — lowercase, strip to `[a-z0-9_]`, collapse
   repeats, trim to 32. Fall back to the email local-part, then to
   `user_<short id>`. On collision append an incrementing numeric suffix.
3. Apply the unique index and set `NOT NULL`.

Validation on write: 3–32 chars, `^[a-z0-9_]+$`, case-insensitively unique.
`409 username_taken` on collision. `display_name` is retained as the free-text
display label; `username` is the stable handle.

## 5. Avatar (migration `0017_avatar.py`)

Add `users.avatar_url`, `Text`, nullable.

```
POST   /api/v1/users/me/avatar   multipart/form-data -> {avatar_url}
DELETE /api/v1/users/me/avatar                       -> 204
```

Uploads to a Supabase Storage bucket `avatars`, keyed `{user_id}/{uuid}.{ext}`.
This is the **first real Storage integration** — `supabase_client.py:9` notes
Storage was planned but unimplemented — so the storage helper it needs is built
here and left reusable for review photos in a later slice.

Constraints: `image/jpeg|png|webp` only, sniffed from content rather than
trusted from the client; max 5 MB; replacing an avatar deletes the prior object.

## 6. Phase A verification

Per the existing project protocol, and the phase is not done until observed:

1. `pytest` — the current 159 tests still pass, plus new tests covering: OTP
   happy path for both purposes, expiry, single-use, attempt-cap **with Redis
   unavailable**, no-enumeration on unknown email, username slug collisions,
   avatar type and size rejection.
2. `ruff` clean.
3. Migrations `0015`–`0017` apply on both local Postgres and Supabase, and
   `0016`'s backfill produces unique handles for all existing rows.
4. `python -m scripts.export_openapi` regenerated, then `npm run gen:api` to
   refresh `lib/api-types.d.ts`.
5. `verify_milestones` and `supabase_verify` still green (49/49, 59/59).

Migrations run on the **session** pooler (`:5432`), runtime on the
**transaction** pooler (`:6543`) — session mode caps at 4 clients.

---

# Phase B — Frontend

## 7. Token layer — adopted from the Claude Design System

The `bluntly.ph Design System` project
(`0cc9dd31-e28a-4dde-967f-b5fa02282f0f`, reachable via `DesignSync`) contains
tokens transcribed literally from the `.fig`. **These are authoritative and are
adopted verbatim** — the token layer is not hand-authored.

Vendored into `app/tokens/` and imported by `app/globals.css`:

| Source | Contents |
|---|---|
| `tokens/colors.css` | base neutrals, brand orange ramp, semantic colors, and the `--surface-*` / `--text-*` / `--accent-*` aliases components consume |
| `tokens/typography.css` | Poppins/Bebas/Arial stacks, weight names, and the `--text-2xs`…`--text-3xl` scale |
| `tokens/effects.css` | 4→48px spacing scale, radii (`5/12/16/32/circle`), the three shadow recipes, motion easing/durations |

Tailwind v4's `@theme` maps these existing custom properties into utilities, so
there is a single source of truth for every value and the DS can be re-synced
later without a rewrite.

Key facts this corrects from the pre-DS assumptions:

- Brand orange is **`rgb(239,88,33)`**, not the `#EF782D` measured off the login
  gradient. That measurement was a *gradient stop*, not the brand color. Solid
  actions use `--accent-primary`; the login gradient is kept literal.
- The app surface is **gray-100 `rgb(242,242,242)`**, not white. White is
  reserved for cards and sheets that must lift off that gray.
- Line-height is a flat **100%** nearly everywhere; `12px` is the *most common*
  text size, not a detail size.
- Borders are almost never solid strokes — a 1px **inset** hairline at 10–30%
  ink is the house style.

Fonts load via `next/font/google` (Poppins, Bebas Neue) rather than the DS's
`@import`, so Next self-hosts them and avoids the render-blocking request. The
scaffold's Geist fonts are removed.

### 7.1 Components: tokens adopted, implementations re-written

The DS components (`Button`, `Card`, `Avatar`, `Chip`, `StarRating`,
`VerifiedBadge`, `SearchBar`, `BottomSheet`, `ActionMenuFab`,
`CategoryFilterRow`, `PhotoStripBanner`, `Icon`) are **styled with inline React
style objects**. Inline styles cannot express media queries, `:hover`,
`:focus-visible`, or `prefers-color-scheme` — precisely what the responsive
shell and the breakpoint-driven dark mode require. Their press states also use
`onMouseDown`, which never fires on touch.

Therefore: **the DS component JSX is treated as reference, not vendored code.**
Each component this slice needs is re-implemented in Tailwind v4 against the
same CSS variables, adding real focus-visible rings, touch-safe press states,
and dark-mode variants. Every radius, shadow, color, and spacing value is taken
from the tokens — none are re-invented.

`assets/logo/bluntly-logo.png` and `assets/icons/icon-data.js` **are** used
directly; they are extracted artwork, not styling.

### 7.2 What the design system does not cover

Verified against its own readme, and important because it bounds what can be
adopted:

- **The auth screens.** The DS import was scoped to 93 Page-1 frames. The 14
  Login/Signup frames carry far higher node ids (`5348`–`5407`) and the readme
  asserts *"No gradients on the mobile app"*, yet the login frame is a full
  orange gradient. Those frames postdate the import. Auth screens are built
  from the Figma frames directly, using DS tokens.
- **Desktop.** The readme states Page-2 *"were not read or built against"*. All
  ~20 dark desktop frames sit outside the DS.
- **Dark mode.** The tokens are light-only, with a single `--surface-inverse`.

### 7.3 Dark mode

Because the DS ships no dark values, a `[data-theme="dark"]` block is authored
on top of the DS aliases — overriding only the semantic layer
(`--surface-*`, `--text-*`, `--border-*`), never the base ramps. Values are
measured from the dark desktop frames and the admin dashboard shell.

Light is the default. Dark applies at the `lg` breakpoint and above via a CSS
media query — pure CSS, no JavaScript, no viewport sniffing, no flash. A user
preference is stored in a `theme` cookie, read server-side, stamped as
`data-theme` on `<html>`, and overrides the breakpoint default in both
directions. Follows
`node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md`.

## 8. API layer

- `lib/api/client.ts` — `server-only` fetch wrapper. Attaches
  `Authorization: Bearer`, parses `application/problem+json` into a typed
  `Problem`, throws `ApiError` carrying `code`.
- `lib/api/errors.ts` — the `code` union from `FRONTEND_INTEGRATION.md` §3 plus
  the four new OTP codes. **Call sites branch on `code`, never on message text.**
- Types from the regenerated `lib/api-types.d.ts`.
- `lib/money.ts` — money is a string-encoded decimal on the wire; never
  `Number()` it for arithmetic. Slice 1 only formats.

## 9. Session

Backend-for-frontend with an httpOnly cookie. The JWT never reaches JavaScript.

| File | Responsibility |
|---|---|
| `app/actions/auth.ts` | `login`, `register`, `requestOtp`, `verifyOtp`, `logout` Server Actions, driven by `useActionState`. Password login posts `application/x-www-form-urlencoded` with `username=<email>`. |
| `lib/session.ts` | `server-only`. Sets/clears the cookie: `httpOnly`, `Secure`, `SameSite=Lax`, `path=/`, `maxAge` = the backend's `expires_in`. |
| `lib/dal.ts` | `verifySession()` and `getUser()`, both React-`cache`d. `getUser()` calls `GET /auth/me` each request pass so a role change takes effect immediately — a role baked into a stale token is never trusted. |
| `proxy.ts` | Next 16 renamed Middleware to Proxy. Optimistic redirects only: cookie presence, no decoding. The Next docs are explicit that proxy is not a session-management solution. |
| `app/api/bff/[...path]/route.ts` | Forwards client-initiated calls with the token attached, so client components never hold it. |

Because both `otp/verify` and `login` return the same `TokenResponse`, session
creation is one function regardless of which path the user took.

No refresh token exists; `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 1440. On
`401` with `code: "token_expired"`, clear the cookie and redirect to login.

## 10. Shell, routing, screens

Route groups: `(marketing)` for public pages, `(auth)` for the auth flows.

One shell tree serves both breakpoints — mobile top bar and bottom nav below
`lg`, desktop header and footer at `lg` and above. CSS-driven; not two parallel
component sets.

Screens built in this slice:

- **Mobile**: OTP request (gradient hero + sheet), OTP code entry, the
  onboarding wizard reduced to username + avatar + password, login.
- **Desktop**: sign up (email, username, password), log in.

Figma's export is absolutely positioned. Every component is rebuilt as flow
layout so it reflows at real viewport sizes.

Primitives: `Button` (pill, h56, disabled at 14% ink), `TextField` (h48, r12,
label + `errors[]` wiring), `OtpInput`, `AvatarUpload`, `Sheet`
(rounded-top-32 with grabber), `Logo`, `ThemeToggle`.

## 11. Environment

```
# frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
SESSION_COOKIE_NAME=bluntly_session

# backend, added by this slice (all present in the root .env)
EMAIL_PROVIDER=resend           # console | resend; tests pin console
RESEND_API_KEY=re_...
EMAIL_FROM=onboarding@resend.dev   # shared sender; swap once bluntly.ph is verified
OTP_TTL_SECONDS=600
OTP_MAX_ATTEMPTS=5
```

PayPal credentials are **backend-only** and already present in the root `.env`
(`PAYOUT_PROVIDER`, `PAYPAL_BASE_URL`, `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`).
PayPal here is a *payouts* adapter (`backend/app/adapters/paypal.py`,
`backend/app/core/config.py:153-158`) — money moves out to reviewers; there is
no checkout. The frontend touches money only via
`PATCH /api/v1/auth/me/payout-account` and `GET /api/v1/payouts`, both in a
later slice. No PayPal value is ever exposed as `NEXT_PUBLIC_*`.

The backend and frontend share the repo-root `.env`
(`backend/app/core/config.py:41-48`, `extra="ignore"`). It is gitignored at
`.gitignore:34`.

## 12. Phase B verification

Against the live backend, per the chosen protocol:

1. FastAPI local against Supabase (`USE_SUPABASE=true`),
   `CORS_ORIGINS=http://localhost:3000`.
2. Register via **email OTP** end-to-end: request a code, receive the real
   Resend email at the account owner's address, verify, land authenticated. The
   user exists in Supabase. (With `EMAIL_PROVIDER=console`, the same run reads
   the code from the log — use this for any address that isn't the Resend
   account owner's.)
3. Register via **desktop password** signup; both accounts appear correctly.
4. Session cookie is `HttpOnly` and unreadable from `document.cookie`.
5. An authenticated page renders the user from `GET /auth/me`, with the chosen
   username and uploaded avatar.
6. A deliberately invalid registration returns `422 validation_error` and the
   `errors[]` entries render against the correct fields.
7. A wrong OTP code six times returns `otp_attempts_exceeded` and the UI shows
   it correctly.
8. Logout clears the cookie; protected routes redirect to login.
9. Both breakpoints: light below `lg`, dark at and above, toggle overrides both.
10. `npm run build` and `npm run lint` pass.

## 13. Open items carried forward

- Rotate the PayPal sandbox credentials and the Resend API key before going
  live; both were shared in a chat transcript. The Resend key is a **live**
  credential, not a sandbox one.
- **Verify the `bluntly.ph` domain in Resend.** Until then `onboarding@resend.dev`
  delivers only to the account owner's address, so OTP signup cannot be tested
  with any other recipient.
- Record the Figma divergences in `docs/DEVIATIONS.md`: OTP is email not SMS,
  and the checkmark logo is dropped.
- Update `docs/schema.md` and `docs/FRONTEND_INTEGRATION.md` for the three new
  migrations and the new endpoints — `schema.md` is already known to lag.
- The `claude_design` MCP is configured in `.mcp.json` but unauthenticated;
  `/design-login` must be run in a fresh session before that project can be
  imported.
