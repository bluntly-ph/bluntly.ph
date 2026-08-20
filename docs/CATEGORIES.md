# Product categories

Fourteen slugs, defined in **three places that must change together**:

| Where | Job |
|---|---|
| `backend/app/core/categories.py` | The vocabulary the API validates against. **Source of truth.** |
| `lib/landing-data.ts` (`CATEGORIES`) | The chips on `/categories` and `/search` — what a product can be *browsed* under. |
| `lib/interests.ts` (`INTERESTS`) | Onboarding step 2 — what a user can express an *interest* in. Stored on `users.interests`. |

`backend/tests/test_categories.py` reads both frontend files off disk and fails
on drift in either direction: a chip the API would reject, an interest that
matches nothing, a slug the API accepts that no page renders, or an interest
with no chip to browse it under.

`trending` is in `landing-data.ts` but is **not** a category. Both pages filter
it out explicitly; it labels a rail.

## Why they are coupled

Two columns hold these slugs and get compared to each other:

* `users.interests` — chosen in onboarding, written by the frontend.
* `products.category` — set by moderators when canonicalising, or by seeds.

`/search?category=<slug>` filters the review feed on `products.category`. A
product tagged with a slug no frontend list shows is not an error anywhere — it
is simply unreachable.

## The incident this prevents

`seed_showcase.py` tagged four products `"electronics"`. Every frontend list
said `"electronics-tech"`. So `/categories` linked to
`/search?category=electronics-tech`, that filter matched nothing, and four of
the six public showcase reviews — the MacBook Air, the Akko keyboard, the Anker
power bank, the Jisulife fan — could not be reached by clicking the category
they belonged to.

Every page returned HTTP 200. No test failed. `products.category` was
`String(120)` with no constraint and the backend had no notion of a valid
category, so there was nothing to fail.

The fix landed in two halves, because they answer different questions:

* **Write** is strict — `ProductCreate` and `ProductCanonicalize` refuse a slug
  the frontend cannot render, so the bad spelling cannot be stored again.
* **Read** is forgiving — the feed filters through `spellings_for()`, so a row
  still holding a legacy spelling is found under its canonical slug. This is
  what makes the site correct before migration `0027` has run anywhere.

## `ALIASES` holds observed mistakes, not guesses

Only spellings that actually reached the database. A guessed alias is a guess
about what somebody meant, and guessing wrong files a product under the wrong
category silently — the same failure the module exists to end. `"home"` is the
clearest example of one that is *not* there: it could mean `home-living` or
`home-appliances`, and nothing in the data says which.

## Adding a category

1. Add the slug and label to `CATEGORIES` in `backend/app/core/categories.py`.
2. Add it to `CATEGORIES` in `lib/landing-data.ts` with a Phosphor icon, so it
   can be browsed.
3. If it should also be an onboarding interest, add it to `INTERESTS` in
   `lib/interests.ts` with a 24×24 icon path.
4. `cd backend && pytest tests/test_categories.py`.

## Renaming one

Don't, unless you migrate both columns. `users.interests` holds slugs chosen by
real people, and a rename orphans their stored preferences as surely as it
orphans the products. If unavoidable: add the new slug, write a data migration
for `products.category` *and* `users.interests`, add the old spelling to
`ALIASES`, and remove the old slug only in a later change.
