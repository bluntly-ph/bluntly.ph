---
name: verifying-frontend
description: Use when asked to verify, test, smoke-test, or confirm the bluntly.ph frontend works — after changing any page, component, route guard, auth flow, or dependency, and before claiming any frontend change is done.
---

# Verifying the frontend

## Overview

**A build that compiles is not a frontend that works.** A component that throws during render
still compiles, still lints, and still returns 200 behind an error boundary. Four gates, each
catching what the previous cannot.

**Run `npm run test:e2e` first** — the Playwright suite in `e2e/` automates gates 2–4 for the
signed-out surface (26 tests). It does not cover anything behind login; see `e2e/README.md`.
Use the manual gates below for what it misses, or when diagnosing a failure it reports.

## The four gates

| Gate | Command | Catches | Blind to |
|---|---|---|---|
| 1. Static | `npm run build`, `npx tsc --noEmit`, `npm run lint` | type errors, lint rules, build failures | anything at runtime |
| 2. Routes | HTTP GET each route, `-MaximumRedirection 0` | 500s, wrong redirects, missing guards | whether the page *renders* |
| 3. Browser | Playwright MCP: `browser_navigate` → `browser_snapshot` + `browser_console_messages` | blank pages, hydration errors, runtime exceptions, missing content | whether multi-step flows work |
| 4. Flows | Playwright MCP: `browser_click` / `browser_fill_form` across pages | dead round-trips (see `?next=` below) | — |

**Stopping at gate 1 or 2 is the default failure.** State which gates you ran.

## Running it

```powershell
npm run dev:all      # API :8000 + web :3000, idempotent (frees ports first)
npm run dev:stop     # when done
```

Gate 2, all routes at once — **never truncate the output**, see Traps:

```powershell
foreach ($r in @('/','/about','/search','/questions','/requests','/reviews/new','/dashboard')) {
  try { $x = Invoke-WebRequest "http://localhost:3000$r" -UseBasicParsing -MaximumRedirection 0 -ErrorAction Stop
        "{0,-16} {1}" -f $r, $x.StatusCode }
  catch { "{0,-16} {1} -> {2}" -f $r, $_.Exception.Response.StatusCode.value__, $_.Exception.Response.Headers.Location }
}
```

Expected: public routes **200**; gated routes **307 → `/login?next=<path>`**; unknown **404**.

Gate 3, per page: `browser_navigate` → `browser_snapshot` (accessibility tree — assert on real
content, not pixels) → `browser_console_messages` with `onlyErrors: true`.

## What must be true

- **27 routes** exist under `app/`. Gated: `/dashboard`, `/profile`, `/moderate`, `/onboarding`,
  `/reviews/new`, `/questions/new`, `/requests/new`.
- Auth guards live in **two** places and both matter: `proxy.ts` (`PROTECTED` array, optimistic
  cookie check, sets `?next=`) and `lib/dal.ts::requireUser` (real backend verification).
  **A new protected route must be added to `proxy.ts`**, or it still redirects but silently loses
  the return path.
- `?next=` must survive the whole OTP round-trip: `proxy.ts` → `/login?next=` → hidden input in
  `SignupForm` → `CodeStep` → `verifyOtp`. It was dead end-to-end once — set but never read — and
  only gate 4 or reading every hop catches that. Gates 1–3 all passed while it was broken.

## Traps that produce false results

| Trap | Why it lies | Do instead |
|---|---|---|
| React `eval() is not supported` console error | Dev-only. `next.config.ts` omits `unsafe-eval` on purpose; prod React never calls eval. | Ignore. **Never add `unsafe-eval` to silence it.** |
| `\| Select-Object -Last 25` on lint/test output | Hides earlier failures. Two lint errors in different files reported as one. | Filter by pattern, or print all. Read the count line. |
| Grepping `_next/static/css` to check styling | Dev serves CSS from a chunk path. Absence means nothing. | Check for `rel="stylesheet"` and a known token like `--text-primary`. |
| Running `scripts.verify_milestones` in PowerShell | It shells out to `grep` (line ~390), absent from PowerShell PATH → `FileNotFoundError` **after** PASS lines. Looks like a real failure. | Run it from **Git Bash**. |
| HTTP 200 as proof of rendering | Error boundaries return 200. | Gate 3. |
| Redis `rate limiter unavailable` in logs | Expected — no local Redis, fails open by design. | Ignore. |

## Common mistakes

- Claiming "frontend verified" after gate 1. **State which gates ran.**
- Reporting a finding without confirming it the opposite way first.
- Using `browser_run_code_unsafe` — use `browser_evaluate` for scoped page JS.
- Leaving dev servers running without saying so.

## Setup

Playwright MCP is in `.mcp.json` (headless, `--isolated` — never touches a real Chrome profile).
**It loads on Claude Code restart**; if `browser_*` tools are absent, restart first. Output goes
to `.playwright-mcp/` (gitignored).
