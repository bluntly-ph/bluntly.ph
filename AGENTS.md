<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:fmd-build-frontend -->
# Bluntly.ph; Frontend Build Guide (agents)

> Materialized from [`docs/frontend/build-bluntly-fe.md`](docs/frontend/build-bluntly-fe.md).
> Edit that canonical doc and re-materialize; do not treat this file as the source of truth.

## Scope; frontend only

This is a monorepo. The **Next.js frontend** is at the repo root (`app/`, `lib/`, `public/`);
the **FastAPI backend** is in `backend/` and is a separate track, already built through M3.

- **Edit only:** `app/`, `lib/`, `public/`, root frontend config (`next.config.ts`,
  `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `package.json`), and
  `docs/frontend/`. Root `README.md`, `BRAND.md`, `DESIGN.md`, and this `AGENTS.md` are
  materialized from canonical docs, not hand-edited.
- **Read-only contract:** `backend/` code and the backend docs in `docs/`
  (`ARCHITECTURE_AS_BUILT.md`, `schema.md`, `adr/`, `MILESTONES.md`, `M*_TEST_PLAN.md`,
  `PRODUCTION.md`, `superpowers/`). Consume the API only through `docs/openapi.json` and
  `docs/FRONTEND_INTEGRATION.md`. **Never edit backend code or backend docs.**
- Missing backend behavior (for example password-reset or Q&A endpoints; see PRD §8)? Raise it
  as a backend ask; do not implement it from this track.

## Read order (start every session at the index)

1. `docs/frontend/index.md` (manifest)
2. `docs/frontend/prd-bluntly-fe.md` (what to build; screen inventory; `PRD-F#`)
3. `docs/frontend/sdd-bluntly-fe.md` (architecture; API client; state; error contract)
4. `docs/frontend/dsd-bluntly-fe.md` + root `DESIGN.md` / `BRAND.md` (visual + UX rules)
5. `docs/frontend/qad-bluntly-fe.md` (tests; per-milestone release criteria)
6. `docs/frontend/build-bluntly-fe.md` (this guide, in full)

Backend contract: `docs/FRONTEND_INTEGRATION.md`, `docs/openapi.json`.

## Stack (pinned) & the currency rule

Next.js **16.2.10** (App Router), React **19.2.4**, Tailwind **v4** (CSS-first `@theme`),
TypeScript **^5**. State to add: **Zustand** + **TanStack Query**. Fonts: **Poppins** via
`next/font/google` (replaces the scaffold's Geist). Types come from `npm run gen:api`
(openapi-typescript over `docs/openapi.json` → `lib/api-types.d.ts`).

Do not rely on training memory for Next.js/React APIs; read `node_modules/next/dist/docs/`
for 16.2.10 first. Tailwind is **v4** (no `tailwind.config.js` theme; use `@theme` in
`app/globals.css`).

## Always / Never

**Always:** route backend calls through one typed API client that branches on the RFC 9457
`code` (never the message); surface API `errors[]`/`reasons[]`; render user and AI-critique
content as escaped text (never `dangerouslySetInnerHTML`); link buy buttons to
`referral_redirect_url` only; meet WCAG 2.1 AA (no orange body text on white); treat money as a
decimal string.

**Never:** edit `backend/` or backend docs; commit secrets (only `NEXT_PUBLIC_*` client-side);
use a Next/React API from memory without checking the local docs; do float math on API money.

## Definition of Done

Implements the `PRD-F#`/`US-##` acceptance criteria; conventions verified against the pinned
stack; QAD happy + sad (+ abuse) paths covered; `npm run lint`, `tsc --noEmit`, Vitest, and
Playwright happy paths pass; no backend files touched. Full detail in the canonical BUILD guide.
<!-- END:fmd-build-frontend -->
