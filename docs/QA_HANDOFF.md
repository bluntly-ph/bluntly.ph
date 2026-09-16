# Independent QA handoff — frontend freeze

**Status: FRONTEND ENGINEERING VERIFICATION COMPLETE. INDEPENDENT QA: RETEST REQUIRED.**

Engineering verification is not a QA pass. Nothing below should be read as one.

## The candidate

| | |
| --- | --- |
| QA baseline SHA | the head of `main` at handoff — the frontend froze at `4013c0f`, and every commit after it is documentation and audit tooling only, so the deployed bundle is `4013c0f`'s. The release note names the exact deployed SHA. |
| Production | https://www.bluntly.ph |
| Frontend scope | the 49 routes in `lib/site-map.ts` (also `docs/SITEMAP.md`, `/sitemap.xml`) |
| Evidence | `docs/FRONTEND_AUDIT.md` — page results, journey results, state coverage and evidence limits, generated from the harness output |

Do not deploy over this while QA is testing: any new deployment changes the baseline.

## What engineering verified

- **Pages** — all 49 routes at 320, 360, 375, 390, 393, 412, 430, 768, 1024, 1280 and 1440: correct status, no redirect away from the route, no horizontal overflow, no console errors, no broken images.
- **Journeys** — 20 flows driven in a browser at 390 and 1440: search → review / question / seller, tabs, filter and order, the "+" action menu's three destinations, all three composers step by step (including a disabled Continue, a satisfied Continue and walking back), the login return path, profile and dashboard navigation, the moderator rail, the moderator queue's detail pane, and the footer's policies.
- **Figma** — frames read live from the file (`lso4Ri4hDaZxvCebhUqlY5`, account Zienxt, Full seat). Each route is classified in the audit as matched, corrected, an intentional product difference, an owner design difference, or a business route with no frame — with the reason written down.

## Owner design difference — do not "fix" it

The landing hero's **"Earned ₱45.50 today"** pill sits on the **upper-right of the tilted review card**, pinned inside the card's own composition so it travels with the card.

The Figma frame puts that pill *below* the card. The owner asked for the current placement on 2026-09-16. It is **not** a Figma mismatch, and it must survive future Figma synchronisation. Verified at 320 / 360 / 375 / 390 / 393 / 412 / 414 / 430 / 768 / 1024 / 1280 / 1440: attached to the card's corner, never clipped, never viewport-relative, no horizontal overflow.

## What QA should hit first

The critical journeys, on a real phone and a real desktop browser:

1. Search → a review.
2. Search → a question.
3. Search → a seller.
4. Search "+" → Write a review.
5. Search "+" → Ask a question.
6. Search "+" → Rate a seller.
7. Seller page "+" → its actions, and the store dashboard as the store's owner.
8. Write a review — the whole process, ending in a real submission.
9. Rate a seller — the whole process, ending in a real submission.
10. Ask a question — the whole process, ending in a real submission.
11. Sign-in return path: open a guarded route signed out, sign in, land back where you were going.
12. Profile and dashboard navigation.
13. Moderation navigation and the review queue.

Submissions matter most: engineering answered those POSTs in the browser, so **no real submission has been made by the audit**.

## Verification limitations — QA owns these

| What | State | Why |
| --- | --- | --- |
| Authenticated routes on production | HUMAN_AUTH_REQUIRED | Everything signed-in, store-owner and moderator is LOCAL FIXTURE VERIFIED. Production sign-in is an emailed one-time code; engineering has no mail hook and must not create or borrow a session. |
| Seller-dependent routes on production | LIVE-DATA VERIFIED (signed out) | The owner authorised one labelled QA seller on 2026-09-16 — see *Reversible test data in production* below. `/sellers/[id]` now renders live. The store dashboard is still HUMAN_AUTH_REQUIRED: the row is unclaimed, so nobody owns it. |
| Anything that writes | NOT EXERCISED | Review, seller-review and question submission, answering, voting and withdrawal. Verified up to the submit control only. |
| The one-time-code step | NOT EXERCISED | Needs a mail hook. The form, its validation and the return path are verified. |
| Moderator queues other than the review queue | BLOCKED locally | Prices, seller claims, reviewers, users and the activity log have no local fixture payloads, so their populated tables have no evidence. Their shells and unreachable-API states do. |

## Reversible test data in production

Exactly one row was added to production, at the owner's instruction (2026-09-16), so that seller journeys can be exercised against the live stack:

| | |
| --- | --- |
| Table | `sellers` |
| Id | `5e11e700-0000-4000-8000-000000000999` |
| Display name | `Bluntly QA Seller` |
| Platform | `other` — **not** Shopee or Lazada, so it cannot be mistaken for a real merchant |
| Claim status | `unclaimed`, `claimed_by_id` null |
| Reviews / ratings / revenue | none — every aggregate reads null or zero, because nothing was fabricated |
| Live URL | https://www.bluntly.ph/sellers/5e11e700-0000-4000-8000-000000000999 |

It is a directory entry and nothing else: no fake merchant identity, no store URL, no invented ratings, no invented earnings.

**To remove it** (nothing references it while its review count is zero):

```sql
DELETE FROM sellers WHERE id = '5e11e700-0000-4000-8000-000000000999';
```

If QA files real seller reviews against it during testing, delete those first, or the foreign key will refuse — that is the intended safety, not a failure.

## Moderator decision controls — now implemented, and QA owns them

This was raised at the previous handoff as "the review queue inspects a card but cannot act on it". The owner ruled on 2026-09-16 that inspection-only is no longer acceptable, so the controls exist:

| Where | Controls | Endpoint |
| --- | --- | --- |
| Review Queue → detail pane | Publish · Monetize & publish (link + platform) · Reject (reason required) | `POST /admin/reviews/{id}/publish`, `/referral-link`, `/reject` |
| Review Queue → Report tab | Dismiss · Remove content · Restore content · Escalate | `POST /admin/reports/{id}/decision` |

Neither had a Figma frame with controls on it, so both are classified **BUSINESS-REQUIRED / DESIGN-SYSTEM ALIGNED**: built from the console's existing panel, pill and two-step-arming vocabulary rather than invented styling.

**QA must exercise these against real content and watch what they do**, because all six are outward-facing:

- Publishing puts a review on the public site. 2★ or lower routes to the Honesty Fund, higher is approved but unmonetized — the panel states which before the press.
- Monetize & publish attaches an affiliate link and starts a revenue-share contract.
- Rejecting notifies the author with the reason, verbatim.
- Remove content unpublishes the review and puts it *back in the review queue* (by design — an unpublished review that left the queue would be unreachable).
- Resolving a report takes it out of the open queue; it stays readable under `?status=resolved` and in the activity log.
- Every one of them writes a `moderation_logs` row with the actor.

`components/moderation/ModerationQueue.tsx` and `ReportQueue.tsx` — the two unmounted components that called these endpoints with `window.prompt` — were deleted rather than left as a second implementation.

## Known environment-only test failures

Neither is a product defect, and neither was worked around by changing the UI:

- `tests/frontend/telemetry-route.test.mjs` — asserts a source line without the CRLF that Windows checkouts write. Historical, unchanged.
- `e2e/route-guards.spec.ts` "an unknown login email is sent to sign up" — TEST ENVIRONMENT LIMITATION. The local fixture proxy is read-only and answers POST with 405, so the form cannot reach the API. It passes against a stack with a live API.

## Re-running the evidence

```
node --experimental-strip-types scripts/audit-sweep.mjs     # pages; WIDTHS/ONLY/ACCESS/SHOT/OUT
node scripts/journey-check.mjs                              # journeys at 390 and 1440
npx playwright test e2e/journeys.spec.ts                    # the signed-out subset
node --experimental-strip-types scripts/audit-report.mjs --evidence <dir>
npm run sitemap -- --paths                                  # the route list itself
npm run audit:contract                                      # API↔frontend wiring
```

`audit:contract` needs no browser, no database and no session — it reads
`docs/openapi.json` and the source, so it runs on a clean checkout and answers
the same thing every time. `docs/CONTRACT_AUDIT.md` explains what its numbers
do and do not mean.

A route with no usable id reports SKIPPED, never PASS. A route that answers 200 from somewhere else reports FAIL, never PASS.
