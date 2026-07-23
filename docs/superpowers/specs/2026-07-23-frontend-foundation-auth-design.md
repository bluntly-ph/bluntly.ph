# Frontend Slice 1 — Foundation & Auth

**Date:** 2026-07-23
**Status:** Approved, ready for implementation planning
**Design source:** Figma `lso4Ri4hDaZxvCebhUqlY5` (bluntly.ph)
**Backend contract:** `docs/FRONTEND_INTEGRATION.md`, `docs/openapi.json`

## 1. Context

The backend is complete through M3: 52 paths, 62 operations, verified against
Supabase. The frontend is an untouched `create-next-app` scaffold — Next.js
16.2.10, React 19.2.4, Tailwind v4, TypeScript. `lib/api-types.d.ts` is already
generated from the OpenAPI spec.

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

That is far too large for one specification. It is decomposed into sequential
slices; this document specifies **Slice 1 only**. Later slices each get their
own spec → plan → implementation cycle.

### Slice sequence

1. **Foundation & auth** (this document) — tokens, shell, API client, session,
   login/register/logout.
2. Read path — landing, search, categories, review page.
3. Reviewer submission wizard.
4. Seller and question flows.
5. Profile and reviewer dashboard (wallet, payouts, contracts).
6. Request board.
7. Admin/moderator console.

## 2. Design/backend conflicts found

These were verified against the code, not assumed.

| Design shows | Backend reality | Resolution |
|---|---|---|
| Mobile OTP: "We'll text you a code", `Send code` | No OTP endpoint exists. `backend/app/api/v1/routes/auth.py` has only `POST /auth/register` and an OAuth2 password-form `POST /auth/login`. | Replace the code step with a password field. |
| `@username`, unique handle | No `username` column. `backend/app/models/user.py:60` has `display_name String(120)`, nullable, **not unique**. | Map to `display_name`. Do not imply uniqueness in the UI. |
| Avatar upload, "Tap to upload to photo" | No user image field anywhere in `backend/app/models/` or `backend/app/schemas/`. `photo_url` exists only on `review`. | Drop from Slice 1. |
| Mobile light theme, desktop dark theme | n/a | Both built, via mode-aware semantic tokens. |
| `bluntly` (mobile) vs `bluntly.ph` + checkmark (desktop) | n/a | Owner decision: `bluntly` wordmark everywhere. |

The first three are **backend gaps**, filed for a future backend slice: OTP
issue/verify endpoints, a unique `username` column with migration, and avatar
upload to Supabase Storage.

The Figma file defines **zero Figma variables** (`get_variable_defs` returns
`{}`). There is no token system to import; the token layer below is authored by
hand from measured frame values.

## 3. Scope

**In scope:**

- Design token layer and Tailwind v4 theme, light and dark.
- App shell: mobile top bar + bottom nav, desktop header + footer.
- Typed API client with the RFC 9457 error contract.
- Session layer: httpOnly cookie, Server Actions, DAL, proxy, BFF forwarder.
- Screens: login, register, logout. Both breakpoints.
- UI primitives that auth requires: `Button`, `TextField`, `Sheet`, `Logo`,
  `ThemeToggle`.

**Out of scope:** every other frame in the file, and the three deferred backend
gaps above.

## 4. Token layer

`app/globals.css`, Tailwind v4 `@theme`. Two tiers.

**Primitives** (measured from Figma node `5348:2789` and the desktop frames):

```
--brand-500: #EF782D
--brand-gradient: linear-gradient(160.87deg,
    #FFC596 4.73%, #EF782D 36.50%, #963719 79.91%, #3C190F 103.78%)
--ink: #202020            /* used at 100 / 70 / 52 / 30 / 14 % alpha */
--grey-100: #F2F2F2       /* sheet surface */
--grey-300: #D9D9D9       /* grabber */
--radius-md: 12px         /* inputs, cards */
--radius-xl: 32px         /* sheets, pill buttons */
```

Spacing on a 4/8px scale. Gutter 32px at 390px width (content 326px).
Control heights: input 48px, primary button 56px.

Typography is **Poppins** (Regular 400 / Medium 500), loaded via
`next/font/google`. The scaffold's Geist fonts are removed.

**Semantic tokens**, resolved per mode:

```
--color-surface, --color-surface-raised, --color-text, --color-text-muted,
--color-border, --color-accent, --color-disabled-surface, --color-disabled-text
```

Light values come from the mobile frames, dark from the desktop frames.

**Mode resolution.** Light is the default. Dark values are applied at the `lg`
breakpoint and above via a CSS media query on the semantic custom properties —
pure CSS, no JavaScript, no viewport sniffing, no flash. A user-set preference
is stored in a `theme` cookie, read server-side, and stamped as `data-theme` on
`<html>`, where it overrides the breakpoint default in both directions.
Implementation follows `node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md`.

## 5. API layer

- `lib/api/client.ts` — `server-only` fetch wrapper. Attaches
  `Authorization: Bearer`, parses `application/problem+json` into a typed
  `Problem`, throws `ApiError` carrying `code`.
- `lib/api/errors.ts` — the `code` union from `FRONTEND_INTEGRATION.md` §3.
  **Call sites branch on `code`, never on message text.**
- Request/response types are taken from the generated `lib/api-types.d.ts`.
  Regenerate with `npm run gen:api` after any backend change.
- `lib/money.ts` — money is a string-encoded decimal on the wire. Never
  `Number()` it for arithmetic. Slice 1 only formats; later slices compute.

## 6. Session architecture

Backend-for-frontend with an httpOnly cookie. The JWT never reaches JavaScript.

| File | Responsibility |
|---|---|
| `app/actions/auth.ts` | `login` / `register` / `logout` Server Actions, driven by `useActionState`. Login posts `application/x-www-form-urlencoded` with `username=<email>`. |
| `lib/session.ts` | `server-only`. Sets and clears the session cookie: `httpOnly`, `Secure`, `SameSite=Lax`, `path=/`, `maxAge` = the `expires_in` returned by the backend. |
| `lib/dal.ts` | `verifySession()` and `getUser()`, both wrapped in React `cache`. `getUser()` calls `GET /auth/me` on every request pass so a role change takes effect immediately — a role baked into a stale token is never trusted. |
| `proxy.ts` | Next 16 renamed Middleware to Proxy. Optimistic redirects only: checks cookie presence, does not decode or validate. The Next docs are explicit that proxy is not a session-management solution. |
| `app/api/bff/[...path]/route.ts` | Forwards client-initiated calls to FastAPI with the token attached, so client components never need the token. |

There is no refresh token; `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 1440. On a
`401` with `code: "token_expired"`, the session cookie is cleared and the user
is redirected to login.

Because the browser talks to Next rather than FastAPI on all primary paths,
CORS is only relevant to the BFF forwarder's own server-side calls.

## 7. Shell and routing

Route groups: `(marketing)` for public pages, `(auth)` for login and register.

One shell component tree serves both breakpoints. It renders the mobile top bar
and bottom nav below `lg`, and the desktop header and footer at `lg` and above.
This is CSS-driven; there are not two parallel component sets to keep in sync.

Figma's code export is absolutely positioned. Every component is rebuilt as
flow layout — flex and grid — so it reflows at real viewport sizes.

## 8. Environment

```
NEXT_PUBLIC_API_URL=http://localhost:8000    # backend origin
SESSION_COOKIE_NAME=bluntly_session
```

PayPal credentials are **backend-only**. In this system PayPal is a payouts
adapter (`backend/app/adapters/paypal.py`), configured by `PAYPAL_CLIENT_ID`,
`PAYPAL_SECRET`, and `PAYPAL_BASE_URL` in `backend/app/core/config.py:153-158`.
There is no checkout flow. The frontend touches money only through
`PATCH /api/v1/auth/me/payout-account` and `GET /api/v1/payouts`, both in a
later slice. No PayPal value is ever exposed as `NEXT_PUBLIC_*`.

## 9. Verification

The slice is done when all of the following have been run and observed:

1. FastAPI running locally against Supabase (`USE_SUPABASE=true`) with
   `CORS_ORIGINS=http://localhost:3000`.
2. Register a new test user through the UI; the account exists in Supabase.
3. The session cookie is present, `HttpOnly`, and not readable from
   `document.cookie`.
4. An authenticated page renders the user from `GET /auth/me`.
5. A deliberately invalid registration returns `422 validation_error` and the
   `errors[]` entries render against the correct fields.
6. Logout clears the cookie and protected routes redirect to login.
7. Both breakpoints render correctly: light below `lg`, dark at and above it,
   and the theme toggle overrides both.
8. `npm run build` and `npm run lint` pass.

## 10. Open items carried forward

- Backend: OTP issue/verify endpoints.
- Backend: unique `username` column and migration.
- Backend: user avatar upload to Supabase Storage.
- Rotate the PayPal sandbox credentials before going live; they were shared in
  a chat transcript.
- Record the four Figma divergences in `docs/DEVIATIONS.md` during
  implementation.
