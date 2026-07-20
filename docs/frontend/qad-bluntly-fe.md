# QA & Test Plan (QAD): Bluntly.ph Frontend

**Project:** Bluntly.ph Frontend
**Date:** 2026-07-20
**Version:** 0.1
**Owner:** Bluntly.ph frontend track
**Status:** Draft
**PRD:** [prd-bluntly-fe.md](prd-bluntly-fe.md)
**SDD:** [sdd-bluntly-fe.md](sdd-bluntly-fe.md)

---

> Frontend-only QA. Backend behavior is validated by the backend's own plans
> ([`../M1_TEST_PLAN.md`](../M1_TEST_PLAN.md), [`../M2_TEST_PLAN.md`](../M2_TEST_PLAN.md),
> [`../M3_TEST_PLAN.md`](../M3_TEST_PLAN.md)). This plan validates that the UI consumes the
> contract correctly and renders every state. Testers fill the **Result** (PASS/FAIL) and Notes
> columns, matching the backend test-plan format.

- **Tester:** ____________  **Date:** ________  **Build/commit:** ________
- **Run against:** ☐ local (`NEXT_PUBLIC_API_URL=http://localhost:8000`) ☐ staging

## 1. Testing Strategy & Scope

**In scope:** all Must-Have and Should-Have `PRD-F#`; every screen state (empty/loading/error/
success + awaiting-review + critique-loading); auth boundaries; RFC 9457 error-code handling;
cross-browser and responsive parity; WCAG 2.1 AA.

**Out of scope:** backend logic (ranking, fraud, splits, payout scheduling); load testing above
the frontend's stateless scaling; native apps; offline mode.

**Testing levels:**

| Level | Tooling | Owner |
|-------|---------|-------|
| Unit / component | Vitest + React Testing Library | Engineer |
| E2E | Playwright (Chromium, Firefox, WebKit) | Engineer / QA |
| Manual exploratory | Real devices + browsers | QA |
| Accessibility | axe-core in Playwright + manual screen-reader | Engineer / QA |

## 2. Test Environments & Data

**Staging URL:** to be set. **Backend:** local `docker compose up` in `backend/` or staging API.
**Test accounts:** register throwaway users; promote one to moderator via backend SQL (see
`../M1_TEST_PLAN.md` §0). Grant tokens via `POST /admin/users/{id}/tokens` for request-board tests.
**Data policy:** never use production PII; seeded/throwaway accounts only.

## 2.1 Feature coverage map

Every PRD feature maps to the scenarios that test it.

| PRD-F# | Covered by |
|--------|------------|
| PRD-F1 | H-M1-03 (responsive shell), §3.2 responsiveness matrix |
| PRD-F2 | H-M1-04 (landing states) |
| PRD-F3 | H-M1-01, S-M1-01 |
| PRD-F4 | H-M1-02, S-M1-02, S-M1-03 |
| PRD-F5 | S-M1-04 (forgot-password gap) |
| PRD-F6 | H-M1-05 |
| PRD-F7 | H-M2-01 |
| PRD-F8 | H-M2-02, H-M2-07 |
| PRD-F9 | H-M2-03, AI-FE-01..03 |
| PRD-F10 | H-M2-04, S-M2-04 |
| PRD-F11 | H-M2-05, S-M2-01, S-M2-02 |
| PRD-F12 | H-M2-06 |
| PRD-F13 | (Should-Have; blocked on backend, PRD §8) |
| PRD-F14 | H-M3-01 |
| PRD-F15 | H-M3-02, S-M3-04 |
| PRD-F16 | H-M3-03, H-M3-04, S-M3-01, S-M3-02 |
| PRD-F17 | H-M3-05, S-M3-03 |
| PRD-F18 | H-M3-06 |
| PRD-F19 | §3.1 cross-browser + §3.2 responsiveness + §3.3 accessibility matrices |
| PRD-F20 | §6 release criteria (deploy smoke test) |

---

## 3. Core Test Scenarios (by milestone)

### FE-M1; Core layout & auth

**Happy paths**

| ID | Scenario | Steps | Expected | US | Result |
|----|----------|-------|----------|----|--------|
| H-M1-01 | Register | fill sign-up, submit | 201; token stored; routed to dashboard | US-01 | |
| H-M1-02 | Login | valid email/password (form post) | 200; `GET /auth/me` populates user | US-01 | |
| H-M1-03 | Responsive shell | load at 390px and 1280px | mobile bottom-nav; desktop header+footer; no horizontal scroll | | |
| H-M1-04 | Landing | load `/` logged-out then logged-in | correct hero + CTAs per state | | |
| H-M1-05 | Dashboard/profile | open `/me` tabs | reviews/comments/stats render; trust badge from `/users/{id}/trust` | | |

**Sad paths**

| ID | Scenario | Trigger | Expected | Result |
|----|----------|---------|----------|--------|
| S-M1-01 | Duplicate email | register existing email | field error from `422 errors[]` under email | |
| S-M1-02 | Wrong password | bad login | clear inline error; no lockout on first try | |
| S-M1-03 | Expired session | `401 token_expired` on any call | session cleared, routed to `/login` | |
| S-M1-04 | Forgot-password (gap) | open flow | UI renders; documented backend gap surfaced, not a crash (PRD §8) | |

### FE-M2; Core feature screens

**Happy paths**

| ID | Scenario | Steps | Expected | US | Result |
|----|----------|-------|----------|----|--------|
| H-M2-01 | Browse + filter | search, apply filters, sort | results update; `sort=wilson` for "most helpful" | | |
| H-M2-02 | Review detail | open a review | stars, verdict chip, pros/cons, author trust badge, photo | | |
| H-M2-03 | Write review + critique | fill draft, request critique, submit | critique panel shows; 201 with `published_at:null` → "awaiting review" state | US-02 | |
| H-M2-04 | Seller review | complete 4-dimension flow | publishes immediately | | |
| H-M2-05 | Vote | upvote another user's review | optimistic count, reconciles with server | US-03 | |
| H-M2-06 | Affiliate | tap buy on published+monetized review | navigates to `referral_redirect_url` (`/r/{id}`); raw URL never shown | | |
| H-M2-07 | Low-trust badge | product with `low_trust` | badge shown, not hidden | | |

**Sad / abuse paths**

| ID | Scenario | Trigger | Expected | Result |
|----|----------|---------|----------|--------|
| S-M2-01 | Self-vote | vote own review | control disabled; server `409 cannot_vote_own_review` handled | |
| S-M2-02 | Vote rate limit | rapid votes | `429` → back off `retry_after_seconds`, toast | |
| S-M2-03 | Unpublished review | view awaiting review | "awaiting moderator" state, not error (`review_not_published`) | |
| S-M2-04 | Duplicate seller review | second review of same seller | `409 seller_review_exists` handled | |
| AB-M2-01 | XSS in review body | script payload in a review/critique field | rendered inert (escaped); no execution (SDD §8.1 LLM02) | |
| AB-M2-02 | ID swap | change a review/id in a request | server 403/404 respected; UI does not leak others' drafts | |

### FE-M3; Remaining screens & delivery

**Happy paths**

| ID | Scenario | Steps | Expected | US | Result |
|----|----------|-------|----------|----|--------|
| H-M3-01 | Pricing/tiers | open `/pricing` | Special/Founding/Standard; current tier highlighted | | |
| H-M3-02 | Token balance + ledger | open wallet | balance (string decimal) + paged transactions, newest first | | |
| H-M3-03 | Post request | create with sufficient tokens | escrowed; shows `effective_reward` | US-04 | |
| H-M3-04 | Fulfill request | fulfill with own published review | request updates | | |
| H-M3-05 | Earnings/payouts | open earnings | payout list + statuses; payout-account prompt near threshold | US-05 | |
| H-M3-06 | Contracts | view + toggle auto-renew / buyout | states render; buyout accept ends revenue share (confirmed) | | |

**Sad paths**

| ID | Scenario | Trigger | Expected | Result |
|----|----------|---------|----------|--------|
| S-M3-01 | Insufficient tokens | post request over balance | `409 insufficient_tokens`; balance + shortfall shown | |
| S-M3-02 | Invalid request | too-short details | `422 request_invalid`; `reasons[]` rendered verbatim | |
| S-M3-03 | No payout account | wallet near `PAYOUT_MIN_PHP` | prompt to set payout account (else scheduler skips) | |
| S-M3-04 | Money formatting | any money value | parsed as decimal string, never float math | |

## 3.1 Cross-Browser Matrix (PRD-F19)

Run happy paths H-M1/M2/M3 on each. Target: parity, no P0/P1.

| Browser | Version | Desktop | Mobile | Result |
|---------|---------|---------|--------|--------|
| Chrome | latest | ☐ | ☐ (Android) | |
| Firefox | latest | ☐ | ☐ | |
| Safari | latest | ☐ | ☐ (iOS) | |
| Edge | latest | ☐ | n/a | |

## 3.2 Responsiveness Matrix (PRD-F19)

Both breakpoints are designed in Figma; verify no overflow, correct nav, tap targets ≥ 44px.

| Screen | 390px (mobile) | 768px (tablet) | 1280px (desktop) | Result |
|--------|----------------|----------------|-------------------|--------|
| Landing | ☐ | ☐ | ☐ | |
| Auth (login/register) | ☐ | ☐ | ☐ | |
| Search + filters | ☐ | ☐ | ☐ | |
| Review detail | ☐ | ☐ | ☐ | |
| Review creation wizard | ☐ | ☐ | ☐ | |
| Request board | ☐ | ☐ | ☐ | |
| Wallet / earnings | ☐ | ☐ | ☐ | |

## 3.3 Accessibility Checklist (WCAG 2.1 AA, PRD-F19)

- [ ] Contrast 4.5:1 text / 3:1 UI; **no orange body text on white** (DSD §6).
- [ ] Every interactive element keyboard-reachable and operable; visible focus ring.
- [ ] Review wizard fully keyboard-navigable; step changes announced.
- [ ] Star rating and verdict chips expose text values to screen readers.
- [ ] Touch targets ≥ 44x44px.
- [ ] Images have alt text; proof-of-purchase photos labeled.
- [ ] `prefers-reduced-motion` respected.
- [ ] axe-core: 0 serious/critical violations on every Must-Have screen.

## 4. Automation vs Manual

**Automated (CI):**
```yaml
- npm run gen:api        # fail if lib/api-types.d.ts drifts from openapi.json
- npm run lint + tsc --noEmit
- vitest (components; target >80% on core: api client, error mapper, money util, auth store)
- playwright (H-M1/M2/M3 happy paths on Chromium/Firefox/WebKit) + axe-core
```
**CI gate:** PR cannot merge if any check fails.

**Manual / exploratory:** real-device pass (iOS Safari, Android Chrome); keyboard-only pass;
visual check of DSD components; 30-min free-form session per milestone.

## 5. Bug Triage

| Severity | Definition | Action |
|----------|------------|--------|
| P0 Blocker | auth/session broken, data-losing action, security, crash on main flow | cannot launch |
| P1 High | core feature broken, no workaround | cannot launch |
| P2 Medium | degraded, workaround exists | launch, fix next sprint |
| P3 Low | minor visual/copy | launch, backlog |

**Tracking:** GitHub Issues, `bug/P0`..`bug/P3` labels.

## 6. Release Criteria (per milestone Definition of Done)

- [ ] All P0/P1 resolved.
- [ ] All happy paths for the milestone pass against a live backend.
- [ ] Sad/abuse paths behave as specified (error codes handled).
- [ ] FE-M3 only: cross-browser (§3.1) and responsiveness (§3.2) matrices complete; accessibility (§3.3) clean.
- [ ] Automated suite green with ≥80% coverage on core modules.
- [ ] Manual exploratory session found no new P0/P1.
- [ ] PRD §5.6 events verified firing in staging.
- [ ] FE-M3 only: deployed build smoke-tested against production API (PRD-F20).

## 7. AI / LLM Evaluation

The frontend does not run a model; correctness of critique content is the backend's concern.
The frontend eval is limited to safe rendering.

| Eval ID | Input | Expected | Pass |
|---------|-------|----------|------|
| AI-FE-01 | critique returns text with markup/script | rendered as escaped text, no execution (SDD §8.1 LLM02) | no DOM injection |
| AI-FE-02 | critique service unavailable / stub | panel degrades to note; submit still works | submit succeeds |
| AI-FE-03 | review body contains injection-style text | shown as data; drives no client action | inert |

---

## Self-Check

- [x] Every Must-Have PRD feature has at least one happy path.
- [x] Every happy path has a corresponding sad path.
- [x] Abuse paths cover XSS and auth/ID-swap for a public app.
- [x] Cross-browser and responsiveness matrices present (PRD-F19).
- [x] WCAG 2.1 AA checklist present, including the orange-on-white trap.
- [x] Release criteria include the deploy smoke test (PRD-F20) and event instrumentation.
- [x] AI section limited to safe rendering; model correctness left to backend.
