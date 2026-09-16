# Bug Tracker update — engineering pass, 2026-09-16

**Status: ENGINEERING FIX PASS COMPLETE. INDEPENDENT QA: RETEST REQUIRED.**

This is what engineering is asking to be written into the live
**Bluntly.ph - Bug Tracker** (`1CP3qiD1YSTTtKTPWl28dr8AYXcnrV33svCx7s5T2y1s`),
row by row.

> **Why it is a document and not the sheet itself.** The Google Sheets
> connector failed to connect for this whole session (`CONNECT_TIMEOUT`). The
> Drive connector can *read* the workbook — which is how the rows below were
> checked against the live tracker rather than against a stale export — but its
> only write operation replaces a file wholesale. Used on this workbook that
> would flatten every sheet, every formula and every piece of QA evidence in it.
> Refusing to do that is the point; a tracker that loses Eric's steps to
> reproduce is worth less than one that is briefly out of date.

**Engineering owns** Status, Assigned To, Date Fixed and the engineering Notes.
**QA owns** Retest Result. No row below asks for `Retest passed` — that is
Eric's to write, and only after he has rechecked it.

Candidate: **`41b3d2b`** · migrations **0048**, **0049** · production
https://www.bluntly.ph

---

## Bug Log — rows to change

For every row: `Status = Fixed — needs retest`, `Assigned To = Dev`,
`Date Fixed = 2026-09-16`, **`Retest Result` left blank**. Only the Notes differ.

### BUG-029 — Multiple application requests return 404 during page load

> Not reproducible on the current deployment in `41b3d2b`. `npm run link-check`
> requests every internal link and every `/_next` asset on 6 pages: 222 links,
> 77 assets, zero 404s; 4 links redirect to sign-in, which is correct and is not
> this bug. One real cause of 404 navigation targets did exist and is fixed —
> see BUG-030: `/moderate/reviewers` links reviewers by handle and every one of
> those URLs 404'd. QA: rerun signed in with the network panel open; if 404s
> remain, please capture the exact failing URLs — the remaining likely cause is
> chunks from a deployment that happened while the page was open, which no code
> change prevents.

### BUG-030 — Public reviewer profile always shows "not found" (S1)

> Fixed in `41b3d2b`. Reproduced on production first: `/u/marites`,
> `/u/yuceann`, `/u/andreo`, `/u/nadine` all returned the not-found copy.
> Root cause, two parts: the page resolved its subject through the review feed's
> `author_id`, which takes a UUID, so a handle could never match; and a reviewer
> with no published review has no feed row, so a real account answered "not
> found". New `GET /users/public/{handle}` resolves a username or an id,
> case-folded, and does not depend on anything being published.
> Evidence: `backend/tests/test_public_profile_api.py` (9 cases) — including
> that no email, role, staff flag or balance appears in the response, checked by
> key and by value.
> QA: retest `/u/{username}` and `/u/{id}` for a known reviewer, a reviewer with
> no published reviews (expect the profile and an empty state, not a 404), and
> an unknown handle (expect a real 404).

### BUG-031 — Cannot verify double-submit or post-submit behaviour

> Fixed in `41b3d2b`. Reopened rather than left Deferred, and the suspicion was
> right: nothing on the server stopped a second submission. The composer
> disabled its own button, which is not a guarantee — a double tap that beats a
> re-render, a retry on a slow connection, a second tab, or anything posting to
> the API directly created two identical reviews in the queue.
> `create_review` now refuses a second review of the same product by the same
> author while one is still awaiting a decision (409 `review_already_pending`).
> Deliberately narrow: a rejected or published review does not block the next
> one. The composer also guards on a ref rather than on state.
> Evidence: `backend/tests/test_double_submit_api.py` (7 cases), including the
> post-submit state — hidden from the public and the feed, visible to its author,
> present in the moderation queue.
> QA: press Publish twice quickly; expect one review. Then check the
> confirmation, the redirect, and that it appears in the queue.

### BUG-032 — Homepage claims reviewer earnings are public

> Fixed in `41b3d2b`. Bullet 4 of the Trust section now reads "Seller ratings
> and reviewer track records are open for anyone to check." — the owner-approved
> replacement. Earnings are private to the reviewer and to moderators and no
> public surface shows them, so the previous copy was a false transparency
> claim. Evidence: `tests/frontend/trust-copy.test.mjs`, which also fails on a
> paraphrase rather than only on the exact sentence.
> QA: read the four bullets on `/`.

### BUG-033 — In-app back button returns to home

> Fixed in `41b3d2b`. Every in-app back control was a `<Link>` to a hardcoded
> destination. `components/site/BackControl.tsx` goes back through router
> history when this tab has an earlier entry, and falls back to a real route
> when it does not (a deep link opened cold) — rendered as a link before
> hydration so it works without JavaScript. Applied to the review page's phone
> bar (was `/`) and the store page's (was `/search?tab=sellers`). The
> "All questions" link is left alone: it names where it goes.
> QA: Search → review → app Back (expect Search with your results), and a
> review opened directly in a new tab → Back (expect Home).

### BUG-034 — Search bar oversized and misaligned with content

> Fixed in `41b3d2b`. The phone frame's 56px height and a 40rem cap were being
> carried onto a 76rem desktop column, so the field was both taller than needed
> and narrower than the cards under it. The frame's numbers stay on phones; from
> `md` the field is the design system's 48px input height and spans the same
> content column as the category pills and the review cards. Glyph insets are
> unchanged — they are vertically centred and follow the height on their own.
> QA: `/search` at 390, 768, 1024, 1280, 1440, 1920.

### BUG-035 — Edit profile re-runs the whole onboarding flow

> Fixed in `41b3d2b`. New `/profile/edit`: one form, every value already filled
> in — handle, display name, photo, interests — and Save returns to `/profile`.
> Editing and onboarding are different jobs; pre-filling the wizard would have
> fixed the symptom and still walked a member of months through "Search or Ask"
> to change a display name.
> **A bio field is not included**: `users` has no such column, and an input that
> writes nowhere would be worse than the bug. Recorded against BUG-036.
> QA: `/profile` → Edit. Confirm interests are pre-selected, change each field,
> save, and check it holds after a refresh.

### BUG-036 — Profile missing major structural elements vs Figma

> Fixed in `41b3d2b`, against the CURRENT live Figma (5446:4328 / 5446:6398 /
> 5446:6532, re-read 2026-09-16). Now present: the banner band, the 80px avatar
> overlapping it by 34px, the share control, a single combined trust badge
> (mark + level) rather than two pills, the "Joined …" line, and all three tabs
> — Reviews, Comments and Stats — each with its own content inside `/profile`.
> Comments reads a new `GET /users/{id}/comments`; Stats reads the trust
> profile's new `progress` block.
> **Three intentional differences, because the data does not exist:** follower
> count and bio are not stored on `users`; "People helped" and "Buyers guided"
> are not served per member, so the figures are Reviews written / Verified
> reviews / Honesty Score. The frame's "Frequent Interactions" card is not drawn
> — there is no follow graph and no endpoint, so it would be three invented
> faces.
> QA: compare against the current Figma, mobile and desktop.

---

## Rows already "Fixed — needs retest" — rechecked against this candidate

### BUG-001 — Publish button stays disabled

> Rechecked on `41b3d2b`: unchanged and still correct. Submit names the fields
> still outstanding instead of sitting greyed out. Status stays
> `Fixed — needs retest`.

### BUG-004 — Hero ticker and featured card vs Figma  *(QA Retest Result: Fail)*

> **Read this before retesting: the Figma changed.** The owner corrected the
> landing/hero frame on 2026-09-16 and asked for it copied one to one, so the
> current frame — not the screenshot this row was written against — is the
> reference. Group 5446:5126 (375×209) places both annotations inside the card's
> own composition: "How noisy is it?" at the top right, 16px in and 4px down;
> "Earned ₱45.50 today" at the bottom left, flush to the group's left edge at
> y185 of 209.
> Against the four items in the last retest: (1) the vertical gap is gone — the
> pill sits inside the card's composition, so it travels with the card;
> (2) and (3) both annotations carry a DotOutline bullet — orange on the light
> pill, white on the orange pill, because an orange dot on an orange pill is
> invisible; (4) the identity block is `@handle · shield + score` via
> `HonestyScore`, with **no "Verified Buyer" text label**, which is what this
> row asked for.
> Status stays `Fixed — needs retest`. Please compare against the current frame.

### BUG-027 — "Ask a question" missing on mobile Q&A

> **The previous engineering note on this row was wrong** — it described the
> hero grid's md/768px split, which belongs to a different bug. Replacing it
> with the actual evidence, and leaving Eric's QA fields untouched.
> Rechecked on `41b3d2b`: `/questions` renders an "Ask a question" control in
> the page header at every width — it carries no `hidden` or `md:` class — and
> the mobile action menu ("+") offers it as one of its three destinations.
> Status stays `Fixed — needs retest`.
> QA: `/questions` at 390px, and the "+" menu.

### BUG-028 — Uploaded avatar does not persist after refresh

> **The previous engineering note on this row was wrong** — it also described
> the md/768px responsive split, which is not this bug. Replaced with the real
> cause.
> Fixed in `41b3d2b`. The photo never left the browser: the `<input
> type="file">` lived inside step 1 of the onboarding wizard, the form submits
> on step 4, and an unmounted input contributes nothing to a FormData. It
> appeared to work because the preview is a local `blob:` URL. Nothing errored.
> Confirmed on production: **all 18 accounts have `avatar_url` null**, and all
> four storage buckets exist and are correctly configured — so this was never a
> storage problem. The submit input is now a sibling of the other fields that
> outlive their step, and step 1's picker is unnamed so only one `avatar` field
> is ever in the form.
> Evidence: `tests/frontend/avatar-submit.test.mjs`, which fails against the
> previous code on two counts.
> QA: upload an avatar, save, navigate away, hard-refresh, and check the header
> and `/profile`. Also `/profile/edit`, which is now the edit path.

---

## Coverage Checklist — reconciliation

Engineering may refresh the Notes; **the Pass/Fail result stays Eric's**. Rows
whose Bug Log entry is only `Fixed — needs retest` keep their previous Fail
until he rechecks.

| Row | Area | Suggested Notes addition | Result |
| --- | --- | --- | --- |
| 8, 9, 51, 52 | Home hero / featured card | "BUG-004 — the owner corrected the Figma on 2026-09-16; compare against the current frame, not the earlier screenshot. Fix deployed on `41b3d2b`." | leave Fail until retested |
| 39, 40 | Write review — double submit / post-submit | "BUG-031 no longer Blocked: server-side duplicate refusal added, post-submit state covered by `test_double_submit_api`. Deployed `41b3d2b`." | **Blocked → ready to test** |
| 45 | Profile — own profile | "BUG-036 — banner, overlapping avatar, share, single badge, Joined line and all three tabs now present. Followers/bio/People helped/Buyers guided are intentional differences with no data behind them." | leave Fail until retested |
| 46 | Profile — public reviewer profile | "BUG-030 — `/u/{handle}` and `/u/{id}` both resolve; a reviewer with no published reviews is no longer a 404. Deployed `41b3d2b`." | leave Fail until retested |
| 47 | Profile — edit / settings | "BUG-028 avatar now actually submits; BUG-035 Edit no longer re-runs onboarding (`/profile/edit`). Deployed `41b3d2b`." | leave Fail until retested |
| 30 | Auth — signup | "BUG-035 — Edit is `/profile/edit` now; onboarding is first-time only." | leave Fail until retested |
| 12 | Home — Trust section | "BUG-032 — bullet 4 replaced with the owner-approved copy." | leave Fail until retested |
| 6 | Global — back / forward | "BUG-033 — the site's own back control now uses history. Browser back was already correct." | leave Pass |
| 34 | Search — search field | "BUG-034 — desktop height and width refitted; phone unchanged." | leave Fail until retested |
| 60–65 | Visual vs Figma | Still **Not started**. Engineering has source-verified the surfaces it changed (profile, hero, review queue) against the live file; the six systematic passes — typography, colour, spacing, components, states, imagery — have not been run as a sweep. | leave Not started |
| 70 | Accessibility — images & labels | "Static audit on `41b3d2b` found 0 images without `alt` and 0 placeholder-only inputs across `app/` and `components/`. Engineering could not reproduce the failure; please re-run and name the specific element." | leave Fail until retested |
| 66–68 | Performance | "Measured on `41b3d2b` with `npm run page-weight`: `/search` parses 1,174 KB, `/` 910 KB, of which ~650 KB is JavaScript. Transfer is fine (brotli). **Open item — not fixed in this candidate.**" | leave Pass, but see the note |

---

## Hidden prerequisites found in QA-passed rows (§15)

Two rows marked `Retest passed` carry an **ACTION REQUIRED** in their Notes.
Both were checked against production today.

| Row | Prerequisite | State |
| --- | --- | --- |
| BUG-023 | "the review-photos Supabase bucket does not exist yet and must be created" | **Satisfied.** All four buckets exist with the right visibility and limits: `avatars` (public, 5 MB), `product-images` (public, 5 MB), `review-photos` (public, 8 MB), `review-receipts` (**private**, 8 MB). Production holds 3 review photos and 5 receipts, so uploads work. The note is stale and can be cleared. |
| BUG-009 | "0 of 587 products currently have an image set — run `seed_product_images.py`" | **Not satisfied, and the count is stale.** Production has **38 products, 5 with an image** — so 33 still fall through to the placeholder. This is a content gap, not a code defect: the fix that made `image_url` reach the cards is live and correct. Engineering has NOT run the seeding script: writing product imagery to production is a content decision and this is a release, not the moment to take it. **Owner decision required.** |

---

## Genuinely open — not fixed, not hidden

| Item | Why |
| --- | --- |
| **Performance** (§24) | Measured, named, and not fixed. `/search` parses 1,174 KB; 34 client components import Phosphor icons. Reworking the bundle during a release candidate is the wrong time to start. `npm run page-weight` makes the next attempt measurable. |
| **BUG-029 signed-in trace** | Engineering has no production session and must not create one. Verified signed-out; one real cause fixed via BUG-030. Needs Eric's signed-in network capture to close. |
| **Coverage 60–65** (visual sweep) | Not started. Changed surfaces were source-verified against the live Figma; the six systematic passes have not been run. |
| **Product imagery** | 33 of 38 products have no image. See above. |
| **`/r/{id}` affiliate redirect** | Not exercised. Following it registers a real affiliate click against the owner's account, which §19 forbids doing from an automated pass. |
