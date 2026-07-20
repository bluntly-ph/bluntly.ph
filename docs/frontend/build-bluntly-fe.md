# Project Build Guide: Bluntly.ph Frontend

**Project:** Bluntly.ph Frontend
**Date:** 2026-07-20
**Version:** 0.1
**Owner:** Bluntly.ph frontend track
**Status:** Draft
**PRD:** [prd-bluntly-fe.md](prd-bluntly-fe.md)
**SDD:** [sdd-bluntly-fe.md](sdd-bluntly-fe.md)

---

> This guide is the operating manual for whoever builds the **frontend** (human or agent). It
> is materialized to the repo root `AGENTS.md` (frontend scope). Edit this canonical copy and
> re-materialize; never hand-edit the root copy as the source of truth.

---

## 0. Scope (read first); frontend only

**This is a monorepo.** The Next.js frontend lives at the repo root (`app/`, `lib/`, `public/`);
the FastAPI backend lives in `backend/` and is a separate delivery track that is already built
through M3.

**An agent working from this guide works on the frontend only:**

- **Edit only:** `app/`, `lib/`, `public/`, root frontend config (`next.config.ts`,
  `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `package.json`), and
  `docs/frontend/`. Materialized root files `README.md`, `BRAND.md`, `DESIGN.md`, `AGENTS.md`
  are regenerated from their canonical docs, not hand-edited.
- **Treat as read-only contract:** `backend/` (code), and the backend docs in `docs/`
  (`ARCHITECTURE_AS_BUILT.md`, `schema.md`, ADRs, `MILESTONES.md`, the `M*_TEST_PLAN.md` files,
  `PRODUCTION.md`, `superpowers/specs/`). Consume the API through `docs/openapi.json` and
  `docs/FRONTEND_INTEGRATION.md`. **Do not modify backend code or backend docs.**
- If a screen needs backend behavior that does not exist (for example password reset or Q&A
  endpoints, see PRD §8), **stop and raise it as a backend ask** in a note; do not implement it
  in the backend from this track.
- The frontend's `docs/frontend/index.md` is the manifest to start from each session.

## 1. How to Build From These Docs

Read in this order before writing code:

1. `docs/frontend/index.md`; what exists, each doc's status.
2. `prd-bluntly-fe.md`; what to build, the screen inventory, the feature IDs.
3. `sdd-bluntly-fe.md`; how the frontend is architected (client, API client, state, errors).
4. `dsd-bluntly-fe.md` (+ root `DESIGN.md` / `BRAND.md`); visual and UX rules.
5. `qad-bluntly-fe.md`; test matrix and per-milestone release criteria.
6. This guide; stack conventions, patterns, guardrails.

Backend contract references: `docs/FRONTEND_INTEGRATION.md` and `docs/openapi.json`.

**Only build against `Locked` docs.** If a doc you need is `Draft`, flag it; do not guess.

### Traceability map; "to build X, read Y"

| To implement… | Read | Verify against |
|---------------|------|----------------|
| A feature `PRD-F#` | PRD §3/§4 → SDD sections it touches | QAD scenarios for its milestone |
| A screen / UI surface | DSD §4 + PRD §5.1 (states) + §5.2 (nav) | DSD §6 a11y + QAD §3.2/§3.3 |
| An API call | SDD §4 + `docs/FRONTEND_INTEGRATION.md` + `docs/openapi.json` | QAD sad/abuse paths (error codes) |
| The AI critique surface | PRD §7 + SDD §8 | QAD §7 (safe rendering) |

## 2. Subagents

No SAD for this track; the main agent does the work inline.

## 3. Stack Currency & Deprecations

> **Do not rely on training memory for Next.js/React conventions.** This is a customized
> Next.js whose APIs differ from your training data. **Before writing framework code, read the
> relevant guide in `node_modules/next/dist/docs/` for the pinned version.** If you cannot
> verify a convention, say so and ask; do not emit a plausible-but-stale API.

### Pinned stack

| Layer | Technology | Pinned version | Verify against |
|-------|------------|----------------|----------------|
| Language | TypeScript | ^5 | `node_modules/typescript` |
| Framework | Next.js (App Router) | 16.2.10 | `node_modules/next/dist/docs/` |
| UI runtime | React | 19.2.4 | React 19 docs |
| Styling | Tailwind CSS | v4 (`@tailwindcss/postcss`) | Tailwind v4 docs (CSS-first `@theme`) |
| Types | openapi-typescript (`npm run gen:api`) | from `docs/openapi.json` | regenerate on backend change |
| State (to add) | Zustand + TanStack Query | latest at install | verify APIs at install |
| Fonts | `next/font/google` (Poppins) | n/a | replaces the scaffold's Geist |

### Deprecations; DO NOT use the stale form

| ❌ Stale | ✅ Current | Note |
|---------|-----------|------|
| Assuming stock Next.js App Router APIs from memory | Read `node_modules/next/dist/docs/` for 16.2.10 first | root `AGENTS.md` rule; APIs differ from training data |
| Tailwind v3 `tailwind.config.js` theme | Tailwind v4 CSS-first `@theme` in `app/globals.css` | v4 convention |
| Geist font (scaffold default) | Poppins via `next/font/google` | per DSD §2.3 |
| Raw `fetch` scattered in components | one typed API client (SDD §4) | single error-contract handler |

**Fast-moving deps requiring live verification:** Next.js, React, Tailwind, TanStack Query,
Zustand. Verify shapes against current docs every time.

## 4. Golden-Path Patterns

Minimal, version-tagged samples of this project's canonical way. Confirm against §3 before
copying. Replace with links to the real files once they exist.

### Typed API call through the client · *pattern, verify against Next 16.2.10*

```ts
// lib/api/client.ts; single entry point; branches on the RFC 9457 `code`
import type { paths } from "@/lib/api-types";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken(); // from authStore
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) throw await toProblem(res); // parses application/problem+json → {code,...}
  return res.json() as Promise<T>;
}
```

*Why this shape:* one place adds the bearer token and maps every error to a `Problem`; UI
branches on `code`, never on the message (SDD §4).

### Handling the publication gate · *pattern*

```ts
// A 201 with published_at:null is success, not an error.
const review = await apiFetch<ReviewOut>("/api/v1/reviews", { method: "POST", body });
setState(review.published_at ? "published" : "awaiting-review");
```

*Why:* the moderator gate is expected; render an "awaiting review" state (PRD US-02).

### Money is a decimal string · *pattern*

```ts
import Decimal from "decimal.js";
const total = new Decimal(balance).plus(reward); // never Number(balance)
```

*Why:* API money is string-encoded decimal; float math corrupts payouts (SDD §5, DSD tokens).

## 5. Conventions & Guardrails

**Repo layout (frontend):** `app/` App Router routes + layouts · `app/(marketing)` public /
`app/(app)` authed · `lib/api/` client + generated types · `lib/stores/` Zustand · `components/`
UI from the DSD · `public/` assets.

**Naming:** `kebab-case` route segments; `PascalCase` components; `useX` hooks; query keys mirror
resource paths (SDD §3).

**Always:**
- Route every backend call through the typed client; surface API `errors[]`/`reasons[]` to the user.
- Render user and AI-critique content as escaped text; never `dangerouslySetInnerHTML` on it.
- Link buy buttons to `referral_redirect_url` only; never a raw affiliate URL.
- Meet WCAG 2.1 AA per the DSD (no orange body text on white).

**Never:**
- Edit `backend/` or backend docs from this track (§0).
- Commit secrets; only `NEXT_PUBLIC_*` reaches the client.
- Use a Next.js/React API from memory without checking `node_modules/next/dist/docs/` (§3).
- Do float math on API money.

**Tests:** every Must-Have ships with its QAD happy + sad (+ abuse) paths. Run `npm run lint`,
`tsc --noEmit`, Vitest, and the Playwright happy paths before calling a task done.

### Restraint / YAGNI

Stop at the first rung that holds: need it? → reuse existing → stdlib → platform (Next/React) →
installed dep → one line → minimum that works. Never cut input validation, error handling,
security, or accessibility.

## 5.2 Public Surface & Crawler Policy

**Public URL(s):** `https://app.bluntly.ph` (production; a review platform is meant to be found).

### Indexability
- [ ] Public review/product/seller pages render crawlable HTML via RSC/SSR (not empty shells).
- [ ] `sitemap.xml` published; canonical URLs on review/product pages; no accidental `noindex`.

### robots.txt (default: allow search)

| Bot | Rule | Note |
|-----|------|------|
| Googlebot | Allow | web search |
| Bingbot | Allow | web search |
| OAI-SearchBot / Claude-SearchBot / PerplexityBot | Allow | answer-surface visibility |
| GPTBot / ClaudeBot / Google-Extended | Decide later | training crawlers; revisit if content policy requires |

Private authed routes (`/me`, `/dashboard`, `/wallet`, `/earnings`, `/admin/*`) are `noindex`.

### Semantic HTML / a11y
Landmarks, ordered headings, meaningful link text; the same semantics that help assistive tech
help crawlers parse review content.

## 6. Materialization

| Target | File | Notes |
|--------|------|-------|
| Canonical | `docs/frontend/build-bluntly-fe.md` | edit here |
| All agents | root `AGENTS.md` | frontend scope; preserves the existing nextjs-agent-rules block |
| Claude Code | root `CLAUDE.md` | pointer (`@AGENTS.md`) |

Re-materialize whenever this guide changes.

### Definition of Done (one task)
- [ ] Implements the referenced `PRD-F#` / `US-##` acceptance criteria.
- [ ] Verified Next.js/React/Tailwind conventions against §3 (no stale APIs).
- [ ] Restraint ladder applied; no over-built abstraction.
- [ ] Tests pass (`npm run lint`, `tsc --noEmit`, Vitest, Playwright happy paths).
- [ ] No secrets committed; only `NEXT_PUBLIC_*` client-side; API `errors[]` surfaced.
- [ ] Did not touch `backend/` or backend docs.
- [ ] Public deploy? robots/indexability (§5.2) in place.

---

## Self-Check
- [x] §1 read-order matches the docs in `docs/frontend/index.md`.
- [x] §0 Scope enforces frontend-only, backend read-only.
- [x] §3 pins exact versions and points at `node_modules/next/dist/docs/`.
- [x] Deprecations register carries the not-stock-Next.js and Tailwind-v4 traps.
- [x] Golden-path samples are minimal and idiomatic (API client, publication gate, money).
- [x] §5 restraint ladder present; security/validation/a11y not cut.
- [x] §5.2 crawler policy filled for the public app.
- [x] §6 materialization matches what gets generated (AGENTS.md, CLAUDE.md pointer).
