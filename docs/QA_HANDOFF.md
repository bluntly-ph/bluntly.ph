# Independent QA handoff

**Status: ENGINEERING VERIFICATION COMPLETE. INDEPENDENT QA: RETEST REQUIRED.**

Engineering verification is not a QA pass. Nothing below should be read as one.

## The candidate

| | |
| --- | --- |
| QA baseline SHA | named in the release note, and it is the SHA CI went green on. **It is no longer `4013c0f`** — this candidate carries the owner's final verdict of 2026-09-16, which is product change, not documentation. |
| Production | https://www.bluntly.ph |
| Frontend scope | the 49 routes in `lib/site-map.ts` (also `docs/SITEMAP.md`, `/sitemap.xml`) |
| Evidence | `docs/FRONTEND_AUDIT.md` — page, journey and state results from the harness; `docs/CONTRACT_AUDIT.md` — API↔frontend wiring; `docs/FULL_FEATURE_MATRIX.md` — every feature with its status and blocker |
| Migrations | **0048** (half-star and zero ratings) and **0049** (report resolution). Both must be applied before the bundle is served, and the release note records when they were. |

Do not deploy over this while QA is testing: any new deployment changes the baseline.

## What engineering verified

- **Pages** — all 49 routes at 320, 360, 375, 390, 393, 412, 430, 768, 1024, 1280 and 1440: correct status, no redirect away from the route, no horizontal overflow, no console errors, no broken images.
- **Journeys** — 20 flows driven in a browser at 390 and 1440: search → review / question / seller, tabs, filter and order, the "+" action menu's three destinations, all three composers step by step (including a disabled Continue, a satisfied Continue and walking back), the login return path, profile and dashboard navigation, the moderator rail, the moderator queue's detail pane, and the footer's policies.
- **Figma** — frames read live from the file (`lso4Ri4hDaZxvCebhUqlY5`, account Zienxt, Full seat). Each route is classified in the audit as matched, corrected, an intentional product difference, an owner design difference, or a business route with no frame — with the reason written down. The moderator queue was re-read against **6922:837** on 2026-09-16 and rebuilt to its eight columns.
- **The contract** — `npm run audit:contract`: 125 operations, 123 called by the frontend, 0 uncalled, 2 declared not-for-the-browser, 1 flag-gated call with no endpoint (documented). Reproducible on a clean checkout.
- **Tests** — backend 1324 passed / 411 skipped locally, with the skips being the DB-gated half that runs in CI's isolated-database job; frontend 299 passed, including the telemetry source test that used to fail on every Windows checkout.

**The browser journeys above predate this candidate's new surfaces.** Items 14–23 under *What QA should hit first* have no harness evidence at all.

## The landing hero's two annotations — the frame is the authority again

This section reversed on 2026-09-16 and the earlier wording is void. It used to record an owner override placing "Earned ₱45.50 today" on the card's upper right against the frame. **The owner then corrected the frame** — *"the figma for the landing/hero card that we are having a trouble is now good and can be copied one to one"* — so the build follows the file:

| Annotation | Position, from group 5446:5126 (375×209) |
| --- | --- |
| "How noisy is it?" | top right of the card, 16px in from the group's right edge, 4px down |
| "Earned ₱45.50 today" | bottom left, flush to the group's left edge, at y185 of 209 |

Both are **inside the card's own composition**, so they travel with it and cannot drift against the viewport. Verified at 320 / 360 / 375 / 390 / 393 / 412 / 414 / 430 / 768 / 1024 / 1280 / 1440: never clipped, never viewport-relative, no horizontal overflow.

QA should compare against the **current** frame, not against any screenshot taken before 2026-09-16.

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

### New on this candidate — none of it has been exercised against real content

14. **Profile → Comments** (`/profile?tab=comments`). Write a comment under someone's review, then check it appears with the right review headline. Delete it and check it leaves the tab (the thread keeps a "[removed]" slot; the profile shows nothing).
15. **Profile → Stats** (`/profile?tab=stats`). Check the level, the "Level n" chip and the "x of y … to become …" line match the account's real standing, and that the bar never overflows.
16. **Half and zero stars**, in both composers. 0, 0.5 … 5. A zero must submit as a rating and read back as 0, not as blank. Try the keyboard: the control is a radio group, so arrow keys must move through the 11 steps.
17. **Continue with Google** on login and signup: greyed, announced as disabled, and going nowhere when clicked or activated by keyboard.
18. **Log out** from the account menu and from the profile page, then use the back button — nothing authenticated may still be reachable.
19. **Moderate** appears in the account menu for a moderator and an admin, and for nobody else. Then open `/moderate` directly as a plain member: it must refuse, because hiding the link is not the boundary.
20. **Staff roles**: as a moderator or a second administrator, confirm the role controls are not offered and that the endpoint refuses (`root_owner_required`). Only bluntly.ph@gmail.com may grant or revoke.
21. **Review queue decisions** — publish, monetize & publish, reject. Watch what each does to the public site and to the author's notifications. See the section below.
22. **Report decisions** — dismiss, remove, restore, escalate. A removed review must come back into the review queue, not vanish.
23. **The QA seller** at `/sellers/5e11e700-0000-4000-8000-000000000999`, and Rate a Seller against it.

## Verification limitations — QA owns these

| What | State | Why |
| --- | --- | --- |
| Authenticated routes on production | HUMAN_AUTH_REQUIRED | Everything signed-in, store-owner and moderator is LOCAL FIXTURE VERIFIED. Production sign-in is an emailed one-time code; engineering has no mail hook and must not create or borrow a session. |
| Seller-dependent routes on production | LIVE-DATA VERIFIED (signed out) | The owner authorised one labelled QA seller on 2026-09-16 — see *Reversible test data in production* below. `/sellers/[id]` now renders live. The store dashboard is still HUMAN_AUTH_REQUIRED: the row is unclaimed, so nobody owns it. |
| Anything that writes | NOT EXERCISED | Review, seller-review and question submission, answering, voting and withdrawal. Verified up to the submit control only. |
| The one-time-code step | NOT EXERCISED | Needs a mail hook. The form, its validation and the return path are verified. |
| Moderator queues other than the review queue | BLOCKED locally | Prices, seller claims, reviewers, users and the activity log have no local fixture payloads, so their populated tables have no evidence. Their shells and unreachable-API states do. |
| Every decision control on this candidate | NOT EXERCISED | Publish, monetize, reject, dismiss, remove, restore, escalate. Their backends are covered by DB tests in CI; **no decision has been taken against real content by engineering**, and none should be until QA is ready to watch what it does. |
| The profile's Comments and Stats tabs | NOT EXERCISED against real data | The endpoints are covered by DB tests in CI. On production the author needs a session, so a signed-in human has to look. |
| Half and zero star ratings | NOT EXERCISED end to end | The step validation, the schema, the CHECK constraint and the round trip are covered by `test_half_star_ratings`; no rating has been submitted through a browser. |

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

## The moderator console and Figma — what can and cannot be compared

Checked against the live file on 2026-09-16. Of the six frame ids the console was built from, **four no longer exist**:

| Frame | Screen | State |
| --- | --- | --- |
| `5017:2225` Admin/Sidebar | the navigation rail | **exists** — re-read, and the rail matches its four groups |
| `6922:837` Admin Page - Review Queue | the review queue | **exists** — re-read, and the table was rebuilt to its eight columns in its order |
| `5017:1738` | Overview | deleted, no replacement |
| `5017:3758` | the old review queue | deleted, superseded by 6922:837 |
| `6532:278` | Answers tab | deleted, no replacement |
| `4810:16500` | a console frame | deleted |

So a Figma comparison of `/moderate` is available for **the rail and the review queue only**. The Overview and the Answers tab stand on their last reading of frames the file no longer has. That is not a claim they are wrong — it is a statement that nobody, including QA, can check them against Figma today. **Please do not file them as mismatches against a screenshot; there is nothing left to mismatch.**

Where frame 6922:837 draws a figure this build cannot source — views, shares, the globe, flagged voters, the per-voter risk table — the console says so in place rather than printing a plausible number. Each reason is in `components/admin/review-queue-model.ts` and in `docs/FULL_FEATURE_MATRIX.md` rows 8.10, 9.4 and 9.6. **Views in particular are a deliberate boundary, not an oversight**: a moderation decision may not be influenced by reading telemetry, and a backend test enforces it.

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

## Performance — measured, and NOT closed

The owner's report is *"bigat pa rin ng responsive ng website"*. The checks we
had could not see it: Coverage row 66 records a Lighthouse score of 100/100, and
the audit harness confirms no horizontal overflow at any width. Both were true
the whole time. So here is a number instead, from `npm run page-weight` against
production on 2026-09-16:

| page | HTML | JS | CSS | total parsed |
| --- | --- | --- | --- | --- |
| `/` | 164 KB | 647 KB | 99 KB | **910 KB** |
| `/search` | 307 KB | 767 KB | 99 KB | **1,174 KB** |
| `/feed` | 264 KB | 647 KB | 99 KB | 1,010 KB |
| `/categories` | 129 KB | 662 KB | 99 KB | 891 KB |
| `/questions` | 96 KB | 662 KB | 99 KB | 858 KB |
| `/requests` | 72 KB | 666 KB | 99 KB | 836 KB |

**Decompressed bytes — what the browser parses.** The network is not the
problem: production serves brotli, and `/`'s 164 KB of HTML crosses the wire as
20 KB. The problem, if the feeling of heaviness has a cause we can name, is
that **every page parses two-thirds of a megabyte of JavaScript** before it is
interactive, plus a 99 KB stylesheet that is identical on all of them. On a
mid-range phone that is CPU time, and CPU time is what compression does not
help.

One measured contributor: **34 client components import Phosphor icons**, and
an icon imported into a client component ships to the browser.

**This is an open item, not a fixed one.** Nothing in this candidate reduces
those numbers, and reworking the bundle during a release candidate is the wrong
time to start. What the candidate does add is the ability to see it: the
numbers above are reproducible in one command, so the next change can be
measured rather than argued about.

QA should still report anything that *feels* slow, with the page and the
device — the table above cannot tell you which interaction is janky, only how
much code had to be parsed first.

## Known environment-only test failures

- `tests/frontend/telemetry-route.test.mjs` — **fixed on this candidate.** It asserted a source line and split on `\n`, so every Windows checkout failed it on a carriage return while CI passed. The test now strips `\r` first. It was never a product defect and the UI was never changed for it; it simply should not have been a standing red.
- `e2e/route-guards.spec.ts` "an unknown login email is sent to sign up" — TEST ENVIRONMENT LIMITATION, unchanged. The local fixture proxy is read-only and answers POST with 405, so the form cannot reach the API. It passes against a stack with a live API.

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
