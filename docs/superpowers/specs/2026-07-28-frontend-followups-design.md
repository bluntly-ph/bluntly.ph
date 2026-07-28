# Frontend Follow-Ups — Design

> Closes the four open items listed under "Known, intentional non-goals / follow-ups"
> in `FRONTEND_MILESTONES.md:101-110`, plus a brand-mark refresh. Four phases, two
> migrations, one small documentation note.

## Scope

| Phase | Item | Migration | Risk |
|-------|------|-----------|------|
| 0 | Brand mark / favicon | — | none |
| 1 | Remove the seller surface (frontend **and** backend) | `0019` (destructive) | **see §1.3** |
| 2 | Product images — one-time seed, then manual | `0020` | low |
| 3 | Bookmarks + Recent Reads | `0021` | low (additive) |
| 4 | Legal copy | — | low |

---

## Phase 0 — Brand mark

`app/icon.svg` rendered a rounded square with the letter `b`. Replaced with the bluntly
mark: the wave-form `n` from the wordmark (`public/bluntly-logo.png`) set in the brand
ring, `#ef5821` on white.

Drawn as a stroked SVG path rather than `<text>` so it needs no webfont and stays legible
at 16px. `app/icon.svg` is the App Router file convention; SVG icons are emitted with
`sizes="any"` (`node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/01-metadata/app-icons.md:24-26,68`).

**Open:** the SVG is a hand-rebuild of a raster supplied in chat. If it drifts from the
official asset, drop the real file at `app/icon.png` and delete `app/icon.svg` — the
convention accepts `.png` with no code change.

**Acceptance:** the tab shows the ring mark at 16px without the glyph turning to mud.

---

## Phase 1 — Remove the seller surface entirely

**Owner decision, 2026-07-28:** sellers go, backend included. The product is an
affiliate-review platform, not a seller directory.

### 1.1 Frontend
Delete `app/sellers/[id]/page.tsx`, `components/seller/SellerReviewForm.tsx`,
`lib/sellers.ts`. Nothing links to them.

### 1.2 Backend
Delete `backend/app/api/v1/routes/sellers.py`, `backend/app/models/seller_review.py`,
their schemas and services, and unregister the router. Remove the seller-review test module.

### 1.3 Data — migration `0019`, **destructive**

Dropping `seller_reviews` (and the seller trust-rating columns) destroys rows that cannot
be recovered from application code. This step is **applied separately and deliberately**,
after an explicit go-ahead and a `pg_dump` of the affected tables retained outside the
database. Everything else in phase 1 is code-only and reversible via git.

If the row count is non-trivial at execution time, stop and re-confirm before dropping.

### 1.4 Documentation impact

Seller trust ratings are a delivered M2 deliverable in the capstone paper. Removing them
means `MILESTONES.md`, `BACKEND_CAPSTONE_PAPER.md`, `schema.md`, and
`ARCHITECTURE_AS_BUILT.md` must record the feature as **built and later withdrawn by owner
decision**, with the date and reason — not silently deleted. A capstone that quietly loses a
milestone is harder to defend than one that documents a scope change.

**Acceptance:** `next build` clean; no seller route in the App Router table; no seller
endpoints in the OpenAPI schema; regression suite green after the seller tests are removed.

---

## Phase 2 — Product images: one-time seed, then manual

### 2.1 Problem

Every review card renders a hue-tinted placeholder (`components/review/ReviewCard.tsx:44-50`),
so the feed reads as empty. Real product imagery is the highest-leverage visual fix.

### 2.2 The distinction that keeps this honest

Two different images, never merged:

- **Product image** — the merchant's listing photo. Descriptive, applies to the *product*.
- **Proof photo** — the reviewer's own photo of the item they bought. It is the evidence
  artifact behind the review's credibility, applies to the *review*, and is
  reviewer-supplied **only**.

`ReviewDetail.tsx:123` currently labels its image "the reviewer's proof photo". Filling that
slot from a merchant page would manufacture evidence. It stays reviewer-only; the product
image is a new, separately-labelled field.

### 2.3 Shape of the solution

**One-time seed, then nothing.** The running platform never fetches a URL — that property is
preserved exactly as documented. Instead:

1. A **one-off script**, run manually by the owner, resolves images for products that
   already exist and have a `source_url`.
2. Results are stored in Supabase Storage.
3. The script is then done. It is not wired into any request path, background worker, or
   deploy step.
4. **Ongoing**, new products get their image from the moderator, by hand, at link-attach
   time.

### 2.4 Schema — migration `0020`

Added to `products`:

| Column | Type | Notes |
|--------|------|-------|
| `image_url` | `Text NULL` | Supabase Storage URL, never a merchant CDN URL |
| `image_source` | `Enum('seeded','moderator','none')` | provenance, default `none` |
| `image_fetched_at` | `TimestampTZ NULL` | when it was resolved |

`image_source` makes provenance queryable: `seeded` rows came from the one-off pass,
`moderator` rows from a human.

### 2.5 The seed script — `backend/scripts/seed_product_images.py`

Lives in `backend/scripts/`, **not** `backend/app/`, so it is outside the application
package and outside the `M3_TEST_PLAN.md:97` D9 grep surface. Nothing imports it.

- Single `GET` per product, https only, 5s timeout, ≤3 redirects
- `User-Agent: bluntly.ph/1.0 (+https://www.bluntly.ph)` — identifies itself truthfully
- `robots.txt` consulted and honoured
- 512 KB cap on the HTML body
- **SSRF guard:** resolve the hostname and reject loopback, private, link-local and
  unique-local ranges. `source_url` values are user-submitted, so this holds even for an
  owner-run script
- Parse `og:image`, falling back to `twitter:image`, via stdlib `html.parser` — no bs4/lxml,
  so no dependency resembling a scraper enters the repo
- Fetch the image, validate content-type and size, strip EXIF, upload to Supabase Storage,
  persist the **Supabase** URL
- Idempotent: skips any product that already has an `image_url`
- Rate-limited to one request every 2s, and logs every URL it touches

Explicitly **not** built: proxy rotation, User-Agent spoofing to defeat bot detection,
headless browsers, or JS-challenge solving. Those cross from reading a public meta tag into
evading an access control.

**Expect partial success.** Shopee's pages are bot-hostile and JS-rendered; a meaningful
share will return a challenge page with no usable `og:image`. That is fine — those products
fall to the moderator path. The script reports a hit/miss summary rather than pretending.

### 2.6 Ongoing path — moderator-supplied

`PATCH /admin/products/{id}/image` accepts an upload or a pasted URL, sets
`image_source='moderator'`. Surfaced in the existing `/moderate` affiliate-link form, where
the moderator is already on the merchant page copying the link.

This is the **only** image path in the running application.

### 2.7 Frontend

- `ReviewCard` renders `product.image_url`, falling back to the existing hue placeholder
- `ReviewDetail` keeps the proof photo separate and relabelled
- `next.config.ts` gains `images.remotePatterns` for
  `https://*.supabase.co/storage/v1/object/public/**` (Next 16 syntax,
  `.../02-components/image.md:533-563`)
- **CSP unchanged** — `next.config.ts:21` already allows `*.supabase.co` in `img-src`.
  That is the payoff for caching into Supabase rather than hotlinking a merchant CDN

### 2.8 Documentation note

The anti-scraping mandate (`MILESTONES.md:127`, `BACKEND_CAPSTONE_PAPER.md:61-65`,
`01-bluntly-ph-PRD.md:60,148`) **stands unchanged**. The application still performs no
automated fetch, no scraping of listing/price/commission data, no headless browser, no
proxy rotation, and no marketplace API calls.

One factual footnote is added to `models/product.py:3-5` and `ARCHITECTURE_AS_BUILT.md`:
initial product images were populated once, on `<date>`, by a manually-run script reading
the Open Graph image tag; the script is not part of the running system. Recorded because it
happened, and a one-line accurate footnote costs nothing to defend.

---

## Phase 3 — Bookmarks + Recent Reads

Split by durability:

**Bookmarks — server-side.** They must survive a device change.
- Migration `0021`: `bookmarks` (`user_id`, `review_id`, `created_at`), unique on
  (`user_id`, `review_id`), `ON DELETE CASCADE` on both FKs
- `POST` / `DELETE /api/v1/reviews/{id}/bookmark`, `GET /api/v1/me/bookmarks`
- Frontend: `BookmarkButton` client component through the BFF proxy, a `/saved` page,
  a header entry

**Recent Reads — local.** Ephemeral browsing history with no cross-device value.
- `lib/recent-reads.ts`: localStorage, last 10 review ids, rail on the landing page
- No server, no PII, no reading-history disclosure obligation incurred

**Acceptance:** bookmark survives logout/login; double-bookmark is idempotent, not a 500;
anonymous visitor gets 401; Recent Reads populates with no network call.

---

## Phase 4 — Legal copy

Raises `/privacy`, `/terms`, `/legal`, `/guidelines` from draft to publishable.

- **Affiliate disclosure** — new, and the most consequential item here. A monetised review
  platform needs a clear, prominent statement that "Buy it here" links earn commission.
  Surfaced on review detail, not buried in `/legal`
- **Privacy** — rewritten against RA 10173 (Data Privacy Act of 2012): what is collected,
  retention, data-subject rights, NPC complaint route. Includes the bookmark storage added
  in phase 3
- **Terms / Guidelines** — tightened for internal consistency with the review lifecycle

**No "pending counsel review" marker on the public pages** (owner decision, 2026-07-28) —
that caveat is internal only, and lives here: *these drafts were written by a non-lawyer and
have not been reviewed by counsel.* Recorded in the spec so the status is not lost, and kept
off the rendered pages as instructed.

---

## Testing

**Backend (pytest):**
- seed script: success, 403, timeout, malformed HTML, missing `og:image`, oversize body,
  **SSRF rejection of private/loopback/link-local hosts**, idempotent re-run
- bookmarks: create, delete, list, duplicate is idempotent, anonymous is 401, cascade on
  review delete
- regression: existing suite green after seller-test removal, with the new expected count
  recorded

**Frontend:**
- `next build` clean
- route smoke-check across `/`, `/search`, `/categories`, `/saved`, `/about`, `/faqs`,
  `/privacy`, `/guidelines`, and confirmation that `/sellers/*` 404s
- favicon renders at 16px

## Rollout

Migrations `0020` and `0021` are additive and low-risk. Migration `0019` **drops tables and
is irreversible** — it is applied on its own, after an explicit go-ahead and a retained
`pg_dump`. Phases land as separate commits so any one can be reverted independently.
