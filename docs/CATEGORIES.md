# Product categories

Eight slugs, defined in **two places that must change together**:

| Where | What it is for |
|---|---|
| `backend/app/core/categories.py` | The vocabulary the API validates against. **Source of truth.** |
| `lib/interests.ts` | The same slugs plus label and icon, for onboarding and the categories page. |

`backend/tests/test_categories.py` reads `lib/interests.ts` off disk and fails
if the two lists differ, so drift is caught in CI rather than in production.

## Why they are coupled at all

The slugs are stored in two columns that are compared to each other:

* `users.interests` — chosen in onboarding step 2, written by the frontend.
* `products.category` — set by moderators when canonicalising, or by seed scripts.

`/search?category=<slug>` filters the review feed on `products.category`. A
product tagged with a slug the frontend does not list is not an error anywhere
— it is simply unreachable through category navigation.

## The incident this prevents

`seed_showcase.py` tagged four products `"electronics"`. The frontend has only
ever had `"electronics-tech"`. So the categories page linked to
`/search?category=electronics-tech`, that filter matched nothing, and four of
the six public showcase reviews — the MacBook Air, the Akko keyboard, the Anker
power bank, the Jisulife fan — could not be reached by clicking the category
they belonged to.

Every page returned HTTP 200. No test failed. `products.category` was
`String(120)` with no constraint, and the backend had no notion of a valid
category, so there was nothing to fail. Migration `0027` relabelled the rows.

## Adding a category

1. Add the slug and label to `CATEGORIES` in `backend/app/core/categories.py`.
2. Add the same slug, its label and a 24×24 icon path to `INTERESTS` in
   `lib/interests.ts`, **in the same position** — the test compares order.
3. Run `cd backend && pytest tests/test_categories.py`.

## Renaming one

Don't, unless you also migrate both columns. `users.interests` holds slugs
chosen by real people, and a rename orphans their stored preferences as surely
as it orphans the products. If it is unavoidable: add the new slug, write a
data migration for `products.category` *and* `users.interests`, then remove the
old slug in a later change — and add the old spelling to `ALIASES` so anything
still sending it keeps working.
