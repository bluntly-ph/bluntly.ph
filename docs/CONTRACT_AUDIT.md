# Backend ↔ frontend contract audit

**Status: ENGINEERING VERIFICATION COMPLETE. INDEPENDENT QA: RETEST REQUIRED.**

The owner's P1: *"a full backend↔frontend contract audit of every capability"*.
This is that audit, and it is a **harness, not a reading** — `scripts/contract-audit.mjs`
regenerates every number below from `docs/openapi.json` and the frontend source
on a clean checkout, with no network, no database and no session.

```
node scripts/contract-audit.mjs            # the report below
node scripts/contract-audit.mjs --json     # machine-readable, with the callers
node scripts/contract-audit.mjs --strict   # non-zero exit on an unanswerable call
```

## What it checks, and what it does not

It answers one question in both directions:

- for every operation the backend publishes, is there frontend that calls it;
- for every call the frontend makes, is there an operation that answers it.

Calls are extracted from source and then **routed against the spec the way the
server routes them** — a literal path beats a parameterised one, so
`/reviews/feed` is not counted as a call to `/reviews/{review_id}`. Doing it the
other way round (matching each spec path against the source text) reports every
parameterised path as called the moment any sibling literal appears anywhere;
the first version of the script did exactly that and cheerfully claimed 125 of
125.

**A "called" result means the wire exists.** It does not mean the call is
correct, that the screen around it works, or that a person can reach it. The
HTTP method is not checked against the call site — the fetch helpers pass it in
too many shapes to read statically — so an operation counts as called when its
path is called. Everything stronger is the e2e suite's job and independent QA's.

## Result, 2026-09-16

| | |
| --- | --- |
| Operations in the spec | **125** |
| Called by the frontend | **123** |
| No frontend caller | **0** |
| Not for the browser (declared, with reasons) | **2** |
| Frontend calls with no operation | **0** |
| Calls assembled at runtime (unresolvable statically) | **1** |

### The two operations no page calls, and why that is correct

| Operation | Reason |
| --- | --- |
| `GET /health` | Liveness probe. The platform calls it; no screen should. |
| `GET /r/{review_id}` | The affiliate redirect. A browser *follows* it as a link — it is never fetched. |

Both are declared in the script with their reasons, so a third one cannot appear
silently: an operation that stops being called shows up as **NO FRONTEND CALLER**
on the next run.

### The call with no operation — found here, and removed

The first run of this audit reported one:

```
/api/v1/auth/oauth/google      components/auth/GoogleButton.tsx
```

`GoogleButton` kept the real OAuth hand-off behind `NEXT_PUBLIC_GOOGLE_AUTH`,
"ready" for the day it was wanted. The audit is what made the problem visible:
the backend publishes **no OAuth route at all**, so that branch could only ever
reach a 404 — whatever the flag said. That is not readiness. It is a switch
that ships a broken sign-in the moment someone sets an environment variable, on
the screen where a failure is least recoverable.

The branch is gone. `GoogleButton` is now unconditionally the disabled control
the owner asked for in P0.2, and `tests/frontend/account-menu-guards.test.mjs`
fails if a flag or a navigation comes back. Re-enabling it later is a few lines,
and they should be written against an endpoint that exists — the order is in the
component's docblock.

**This is the audit earning its keep.** Nothing else in the build would have
reported it: the branch type-checks, lints, renders and is unreachable.

### The one call assembled at runtime

```
/api/v1/contracts/{}{}         components/dashboard/ContractActions.tsx
```

`` `/contracts/${contractId}${path}` `` is three real endpoints written once —
`/auto-renew`, `/buyout/accept`, `/buyout/reject`, all three in the spec. Read
by hand and confirmed; no static read can resolve it, and guessing would be
worse than reporting it.

## Coverage by capability

Every capability the owner's P1 names, with the operations behind it and where
the frontend calls them. Counts are the audit's, grouped by the path's first
segment.

| Capability (owner's P1 list) | Operations | Called |
| --- | --- | --- |
| Reviews — structured review, proof of purchase, versions, votes, reports | 17 | 17 |
| Users — profile, trust progression, comments, dashboard, earnings, streak | 11 | 11 |
| Sellers — seller review, claiming, dashboard, removal | 8 | 8 |
| Products — search, comparison, price observations, URL dedup | 7 | 7 |
| Requests — bounty board, hybrid incentives | 7 | 7 |
| Admin: payouts — earnings, batches, retries | 7 | 7 |
| Admin: reviews — publish, reject, unpublish, referral links | 6 | 6 |
| Auth — sign-up, one-time code, session, onboarding | 6 | 6 |
| Questions / answers — Q&A, best answer | 5 | 5 |
| Notifications | 4 | 4 |
| Contracts — revenue share, buyout, auto-renew | 4 | 4 |
| Comments — thread, votes, a member's own | 3 | 3 |
| Admin: users — roles, trust, penalties | 3 | 3 |
| Admin: analytics — platform admin, geographic votes | 3 | 3 |
| Membership tiers | 3 | 3 |
| Internal — cron, traffic, reading telemetry | 3 | 3 |
| Admin: reports — queue and **decisions** | 2 | 2 |
| Admin: price observations — queue and decisions | 2 | 2 |
| Admin: seller claims — queue and decisions | 2 | 2 |
| Admin: contracts — buyout offers | 2 | 2 |
| Admin: affiliate — preview, import | 2 | 2 |
| Payouts — request, history | 2 | 2 |
| Tokens | 2 | 2 |
| Admin: review queue · reviewers · activity · cron runs · commissions · honesty fund · PII retention · integrity providers · seller reviews · requests | 10 | 10 |
| AI | 1 | 1 |
| Postback — affiliate network server-to-server | 1 | 1 |
| Health, redirect | 2 | 0 (declared above) |

## What this audit cannot tell you

Named plainly, because a green table invites the opposite conclusion:

- **Nothing about correctness.** A call that sends the wrong body, reads the
  wrong field, or ignores an error still counts as called.
- **Nothing about reachability.** An operation called from a component mounted
  on no route counts as called. (Two such components existed until 2026-09-16;
  they were deleted rather than left to inflate this number.)
- **Nothing about production.** It reads source and a spec file. Whether the
  deployed build behaves this way is settled by the deployment and by QA.
- **Nothing about the capabilities with no endpoint at all.** An absent feature
  has no operation to be uncalled. Those live in `docs/FULL_FEATURE_MATRIX.md`,
  which is the document that can say MISSING; this one only ever says
  "uncalled".
