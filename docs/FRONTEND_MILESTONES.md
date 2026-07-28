# Bluntly.ph — Frontend Delivery Milestones (FE-M1 – FE-M5)

> The frontend track, built on the completed backend (`MILESTONES.md`, M1–M3) and
> the Figma design system (`lso4Ri4hDaZxvCebhUqlY5`). Strategy: **breadth-first**
> (stand up every screen, then wire + polish) and **fully responsive** (mobile
> matches Figma; every screen also gets a desktop layout). Roadmap:
> `superpowers/specs/2026-07-24-full-site-build-design.md`.
>
> **Stack:** Next.js 16 App Router (Turbopack) · React 19 · Tailwind v4 bridged to
> design tokens (`app/tokens/*.css`) · server components fetch via `lib/api/client.ts`
> (`apiFetch`, httpOnly-cookie token through `lib/dal.ts`); client mutations go through
> the BFF proxy `app/api/bff/[...path]` · Phosphor icons (SSR). Money is string-decimal;
> "Buy it here" always routes through `/r/{id}`, never a raw affiliate URL.
>
> **Live:** https://www.bluntly.ph — Vercel auto-deploys `main` → production.

## FE-M1 — Foundations & Auth
App shell and the full passwordless auth journey.

**As built:** Next 16 App Router with the token-bridged Tailwind theme and the
vendored design system; `SiteHeader` / `SiteFooter` / mobile bottom `MobileNav`;
data-access layer (`lib/dal.ts` — `getUser` / `requireUser` / `requireRole`) reading a
session from an httpOnly cookie; the BFF route for client-side mutations. Screens:
`/login` (email OTP), `/signup`, `/welcome`, `/onboarding` (interest picker + a
visible `StepBar`).

**Acceptance:**
- Request a code → receive OTP email → verify: new accounts land on `/onboarding`,
  returning members on `/` (no re-onboarding loop).
- Signed-out visitors can read the public site; protected routes redirect to login.
- OTP email is branded (real logo) and sent from the dedicated `mail.bluntly.ph`.

## FE-M2 — Public read surfaces
Everything a logged-out reader can browse, wired to live data.

**As built:** `/` landing (hero + ask-anything search, featured review, reading rail,
category grid, CTA) · `/search` (query + category chips + result grid + empty states) ·
`/categories` (routes into filtered search) · `/reviews/[id]` (structured review —
verdict, star rating, pros/cons, target & anti-target audience, proof photo, author
byline; "Buy it here" → `/r/{id}`) · `/u/[id]` public reviewer profiles (identity,
trust standing, their published reviews). Data from `GET /reviews/feed` and
`/reviews/{id}/full`; graceful fallback to curated samples if the API is unreachable.

**Acceptance:**
- Landing and search render real published reviews; category chips filter results.
- Review detail shows the full structured format; the author name links to `/u/{id}`.
- "Buy it here" 302-redirects through `/r/{id}` and never exposes a raw affiliate URL.

## FE-M3 — Reviewer & community flows
The create/participate surfaces.

**As built:** `/reviews/new` — a two-step write flow (find/create the product from a
purchase link → structured review form → submit for moderation) · interactive
up/down voting (`ReviewVoteBar` client + BFF) · Q&A: `/questions`, `/questions/[id]`
(answers, answer form, award best answer), `/questions/new` (product picker +
directed-to) · Review requests / bounties: `/requests` (board + up-vote), `/requests/new`.

**Acceptance:**
- Submitting a review returns it as **awaiting moderation** (never auto-published).
- A vote persists and updates counts; self-voting and double-voting are rejected.
- Ask a question, answer one, mark a best answer; post and up-vote a request.

## FE-M4 — Earnings, profile & moderation
Money, identity, and the admin surface.

**As built:** `/dashboard` — reviewer earnings (wallet in ₱, token balance, payouts,
PayPal payout-account form) · `/profile` — the signed-in user's stats + their reviews ·
`/moderate` — the moderator review queue (publish / reject / attach affiliate link),
role-gated via `requireRole`.

**Acceptance:**
- Dashboard shows wallet + tokens + payout history for the signed-in reviewer.
- A moderator can action the queue; a non-moderator is refused (`/moderate` gated).
- Payout-account (PayPal email) validates before saving.

## FE-M5 — Content, polish & deploy
The pages that make it a real site, responsiveness, motion, and production.

**As built:** editorial + legal pages behind every footer link — `/about`,
`/how-it-works`, `/faqs`, `/contact`, `/articles`, `/privacy`, `/terms`, `/guidelines`,
`/legal` (shared `PageShell` + data-driven `Article` renderer + `.prose` styles) ·
responsive everywhere (mobile-first; desktop nav switches at `md`, fixing the
"looks like mobile when narrowed" issue) · page-transition + entrance animations
(`template.tsx`, reduced-motion aware) · branded favicon (`app/icon.svg`) · deployed
to production on Vercel (auto-deploy on `main`).

**Acceptance:**
- Every header, nav, and footer link resolves (no 404s); curl-verified 200 in prod.
- Layout holds at mobile / tablet / desktop widths.
- The browser tab shows the bluntly mark; navigation feels smooth.

---

## How to check (for reviewers/evaluators)
- **Live site:** https://www.bluntly.ph — browse the landing, open a review, tap a
  category, view a reviewer profile, open any footer page.
- **Routes** are enumerated in the Vercel build output (App Router route table).
- The frontend consumes only the documented API in `FRONTEND_INTEGRATION.md`; the
  backend milestones + their verification are in `MILESTONES.md`.

## Known, intentional non-goals / follow-ups
- **Seller-facing frontend: fully removed (2026-07-28).** Seller trust ratings were a
  delivered M2 milestone (backend, API, and this unlinked `/sellers/[id]` route), then
  withdrawn by owner decision: bluntly.ph is an affiliate-review platform, not a
  seller directory. The route, its form component, and the backend surface behind it
  are deleted (`cf7afbc`, `8936dda`, `9366a5b`); the `seller_reviews` table drop is
  migration `0021_drop_seller_reviews` (written, not yet applied). See
  `docs/MILESTONES.md` for the full withdrawal note.
- **Recent Reads / Bookmarks** — reader conveniences, not yet built (bookmarks need a
  backend surface).
- **Real review photos** — cards/detail show a branded placeholder; enabling remote
  photos needs `next.config` `images.remotePatterns` (CSP already allows `*.supabase.co`).
- **Legal copy** (Privacy / Terms / Legal) is a solid draft pending a real legal review.
