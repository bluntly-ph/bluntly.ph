# E2E tests

```bash
npm run test:e2e        # headless
npm run test:e2e:ui     # interactive runner
```

Needs **both** servers. `npm run dev:all` starts web :3000 + API :8000; the Playwright config
reuses a stack that is already up rather than restarting it.

## What is covered

| Spec | Guards against |
|---|---|
| `route-guards.spec.ts` | Auth redirects, and `?next=` surviving the bounce to `/login` |
| `console-health.spec.ts` | Pages that serve 200 but throw in the browser |

## Why these two

Both target failures the rest of the toolchain cannot see.

**`?next=` was dead end to end** — `proxy.ts` set it, the login page never rendered it, and
`verifyOtp` never read it, so signing in always dumped you on `/`. Build, typecheck, lint and an
HTTP 200 check all passed the entire time it was broken. The failure mode is *silent*: the route
still redirects, so anything checking only status codes goes green. `route-guards.spec.ts` asserts
the query parameter itself, which is the only thing that distinguishes a working guard from a
lossy one.

**A component that throws during render still returns 200** behind an error boundary.
`console-health.spec.ts` asserts on console errors, page exceptions, and computed style, because
those are the only signals that separate "served" from "working".

## What is NOT covered, and why

Every form in the app — product search, review composer, ask-a-question — sits behind an
**email-OTP login**, which cannot be driven end to end without a mail hook. So the searchable and
submittable surfaces are untested here, including the debounced product search whose effect logic
was a source of lint errors.

Closing that gap needs one of:

- a test-only endpoint that mints a session for a seeded user (guard it behind an env flag so it
  cannot exist in production), or
- a seeded token fixture the tests inject as the session cookie directly, or
- a mail-catcher the OTP step can read from.

The first is usually the smallest change and unlocks the whole authenticated surface.

## Conventions

- Assert on **observable behaviour**, not implementation details.
- Ignore dev-only console noise via the `IGNORED` list, and say *why* each entry is there —
  one of them exists because the CSP deliberately omits `unsafe-eval`, and silencing it the
  wrong way would weaken a real XSS mitigation.
- A new protected route needs an entry in `proxy.ts`'s `PROTECTED` **and** in the `GATED` list
  here, or it will lose its return path silently.
