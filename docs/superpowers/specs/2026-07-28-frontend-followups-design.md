# Frontend Follow-Ups — Design

> Closes the four open items listed under "Known, intentional non-goals / follow-ups"
> in `FRONTEND_MILESTONES.md:101-110`, plus a brand-mark refresh. Four phases, two
> migrations, one documentation-amendment pass.
>
> **Owner decision recorded here:** phase 2 reverses the standing "no scraping, ever"
> ruling in a narrow, explicitly-scoped way. See §2.6.

## Scope

| Phase | Item | Migration | Risk |
|-------|------|-----------|------|
| 0 | Brand mark / favicon | — | none |
| 1 | Remove dead `/sellers` frontend | — | none |
| 2 | Product images via link unfurl | `0019` | **elevated** — see §2.6 |
| 3 | Bookmarks + Recent Reads | `0020` | low (additive) |
| 4 | Legal copy | — | low |

Out of scope: the backend `/sellers` API, seller trust ratings, and
`models/seller_review.py` — a completed M2 deliverable that stays.

---

## Phase 0 — Brand mark

`app/icon.svg` currently renders a rounded square with the letter `b`. Replace it with
the bluntly mark: the wave-form `n` from the wordmark (`public/bluntly-logo.png`) set
in the brand ring, `#ef5821` on white.

Drawn as a stroked SVG path rather than `<text>` so it needs no webfont and stays legible
at 16px. `app/icon.svg` is the App Router file convention; SVG icons are emitted with
`sizes="any"` (`node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/01-metadata/app-icons.md:24-26,68`).

**Open:** the SVG is a hand-rebuild of a raster the owner supplied in chat. If it drifts
from the official asset, drop the real file at `app/icon.png` and delete `app/icon.svg` —
the convention accepts `.png` and no code changes.

**Acceptance:** the tab shows the ring mark at 16px without the glyph turning to mud.

---

## Phase 1 — Remove the dead `/sellers` frontend

Delete `app/sellers/[id]/page.tsx`, `components/seller/SellerReviewForm.tsx`, `lib/sellers.ts`.
Nothing links to them; the route was already documented as unlinked and slated for removal.

Update the non-goal note at `FRONTEND_MILESTONES.md:102-105` to record that the frontend
is gone and the API deliberately remains.

**Acceptance:** `next build` clean; no `sellers` route in the App Router table; backend
seller endpoints still answer.

---

## Phase 2 — Product images via link unfurl

### 2.1 Problem

Every review card renders a hue-tinted placeholder (`components/review/ReviewCard.tsx:44-50`).
The feed reads as empty. Real product imagery is the single highest-leverage visual fix.

### 2.2 The distinction that makes this honest

Two different images, never merged:

- **Product image** — the merchant's listing photo. Descriptive. Applies to the *product*.
- **Proof photo** — the reviewer's own photo of the item they bought. It is the evidence
  artifact behind the review's credibility. Applies to the *review*, and is
  reviewer-supplied **only**.

`ReviewDetail.tsx:123` currently labels its image "the reviewer's proof photo". Filling that
slot from a merchant page would manufacture evidence. It stays reviewer-only; the product
image is a new, separately-labelled field.

### 2.3 Schema — migration `0019`

Added to `products`:

| Column | Type | Notes |
|--------|------|-------|
| `image_url` | `Text NULL` | Supabase Storage URL, never a merchant CDN URL |
| `image_source` | `Enum('unfurled','moderator','none')` | provenance, default `none` |
| `image_fetched_at` | `TimestampTZ NULL` | when it was resolved |

`image_source` exists so provenance is queryable — a moderator can tell at a glance which
images the system resolved and which a human supplied.

### 2.4 `app/services/unfurl_service.py`

One function: given a URL, return an image URL or `None`.

- Single `GET`, https only, 5s timeout, ≤3 redirects
- `User-Agent: bluntly.ph/1.0 (+https://www.bluntly.ph)` — identifies itself truthfully
- `robots.txt` consulted and honoured
- 512 KB cap on the HTML body; abort past it
- **SSRF guard (non-negotiable):** resolve the hostname and reject loopback, private,
  link-local and unique-local ranges before connecting. The URL is user-supplied and the
  fetch originates inside our infrastructure
- Parse `og:image`, falling back to `twitter:image`, using stdlib `html.parser` —
  deliberately not bs4/lxml, so `M3_TEST_PLAN.md:97` check D9 stays clean and no dependency
  resembling a scraper enters `backend/app`
- Fetch the image, validate content-type and size, strip EXIF, upload to Supabase Storage,
  persist the **Supabase** URL

Explicitly **not** built: proxy rotation, User-Agent spoofing to defeat bot detection,
headless browsers, or any JS-challenge solving. Those cross from reading a public meta tag
into evading an access control, and they are exactly what D9 greps for.

### 2.5 Integration

Hook: best-effort call inside `referral_service.attach_link` (`backend/app/services/referral_service.py:154`),
which a moderator triggers via `POST /admin/reviews/{id}/referral-link`
(`backend/app/api/v1/routes/admin_referral.py:92`). One fetch per product, moderator-initiated,
never on page view.

**Failure never blocks publish.** On any error the row lands `image_source='none'` and the
moderator supplies the image by hand via a new `PATCH /admin/products/{id}/image`
(upload or URL). Given Shopee's bot-hostile, JS-rendered pages, the manual path should be
treated as a primary path, not an edge case.

Frontend:
- `ReviewCard` renders `product.image_url`, falling back to the existing hue placeholder
- `ReviewDetail` keeps the proof photo separate and relabelled
- `next.config.ts` gains `images.remotePatterns` for
  `https://*.supabase.co/storage/v1/object/public/**` (Next 16 syntax,
  `.../02-components/image.md:533-563`)
- **CSP is unchanged** — `next.config.ts:21` already allows `*.supabase.co` in `img-src`.
  This is the payoff for caching rather than hotlinking the merchant CDN

### 2.6 Reversal of the anti-scraping mandate

This phase contradicts a standing owner ruling. Recording it plainly rather than letting the
docs assert something untrue:

| Source | Current claim |
|--------|---------------|
| `MILESTONES.md:127` | "Owner decision: no scraping, ever." (resolved 2026-07-15) |
| `BACKEND_CAPSTONE_PAPER.md:61-65` | "no web-scraping, no headless browsers, and no marketplace API calls"; "enforced by an automated test" |
| `01-bluntly-ph-PRD.md:60,148` | automated ingestion out of scope; "their ToS prohibit scraping" |
| `models/product.py:3-5` | "No automated fetch of the URL ever happens." |
| `M3_TEST_PLAN.md:97` | check D9 greps for scraping dependencies |

**Owner overrode this on 2026-07-28**, accepting the documentation cost and the Shopee ToS
exposure. Each source above is amended to state precisely:

- **What now happens:** one moderator-triggered HTTP GET of a reviewer-submitted product
  URL, reading the Open Graph image meta tag, result cached.
- **What still never happens:** no scraping of listing, price, or commission data; no
  headless browser; no proxy rotation; no marketplace API calls; no automated bulk crawling.

D9 is amended to keep asserting the absence of `scrapy|selenium|playwright|proxy_rotation`
while permitting the stdlib unfurl. The narrow, documented version is defensible under
examination; a silent one is not.

**Residual risk the owner accepted:** Shopee's ToS prohibits automated access, and this is
automated access, however light. That risk is not engineered away — it is accepted.

---

## Phase 3 — Bookmarks + Recent Reads

Split by durability, decided 2026-07-28:

**Bookmarks — server-side.** They must survive a device change.
- Migration `0020`: `bookmarks` (`user_id`, `review_id`, `created_at`), unique on
  (`user_id`, `review_id`), `ON DELETE CASCADE` both FKs
- `POST` / `DELETE /api/v1/reviews/{id}/bookmark`, `GET /api/v1/me/bookmarks`
- Frontend: `BookmarkButton` client component through the BFF proxy, a `/saved` page,
  a header entry

**Recent Reads — local.** Ephemeral browsing history with no cross-device value.
- `lib/recent-reads.ts`: localStorage, last 10 review ids, rail on the landing page
- No server, no PII, and no reading-history disclosure obligation incurred

**Acceptance:** bookmark survives logout/login; double-bookmark is idempotent, not a 500;
an anonymous visitor gets 401; Recent Reads populates without a network call.

---

## Phase 4 — Legal copy

`/privacy`, `/terms`, `/legal`, `/guidelines` are drafts. This phase raises the floor; it
does not clear them for production use.

- **Affiliate disclosure** — new, and the most consequential item here. A monetised review
  platform needs a clear, prominent statement that "Buy it here" links earn commission.
  Surfaced on review detail, not buried in `/legal`
- **Privacy** — rewritten against RA 10173 (Data Privacy Act of 2012): what is collected,
  retention, data-subject rights, NPC complaint route. Must include the bookmark storage
  added in phase 3
- **Terms / Guidelines** — tightened for internal consistency with the review lifecycle

**This does not constitute legal review.** The "pending counsel review" marker stays. Author
is not a lawyer and the drafts should not be treated as vetted.

---

## Testing

**Backend (pytest):**
- unfurl: success, 403, timeout, malformed HTML, missing `og:image`, oversize body,
  **SSRF rejection of private/loopback/link-local hosts**, and failure-does-not-block-publish
- bookmarks: create, delete, list, duplicate is idempotent, anonymous is 401,
  cascade on review delete
- regression: existing 159-test suite stays green

**Frontend:**
- `next build` clean
- route smoke-check across `/`, `/search`, `/categories`, `/saved`, `/about`, `/faqs`,
  `/privacy`, `/guidelines`
- favicon renders at 16px

## Rollout

Migrations `0019` and `0020` are additive (new column, new table) and low-risk, but they run
against the live Supabase instance and are applied **deliberately**, not as a deploy side
effect. Phases land as separate commits so phase 2 can be reverted without touching phase 3.
