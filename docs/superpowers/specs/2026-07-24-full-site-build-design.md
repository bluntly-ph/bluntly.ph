# bluntly.ph — Full frontend build (design & roadmap)

_Date: 2026-07-24 · Branch: `feat/frontend-foundation-auth`_

## Goal

Build the **entire** bluntly.ph website as functioning, responsive UI/UX from the
Figma (`lso4Ri4hDaZxvCebhUqlY5`) on top of the already-complete backend (M1–M3).
Strategy chosen by the owner: **breadth-first** (stand up every screen, then wire
data + polish) and **fully responsive** (mobile matches Figma; every screen also
gets a desktop layout, like the existing auth pages).

## The product model (corrected — this is NOT e-commerce)

bluntly is an **affiliate-powered honest-review platform**, not a storefront.

- A user who bought a product on **Shopee / Lazada / TikTok Shop / Amazon** writes a
  **structured review** (General Info, Experience, Pros & Cons, "This is not for",
  Verdict, star Rating).
- A **moderator approves** it and attaches an **affiliate link**; the review is then
  **published** and **monetized**.
- Readers read reviews and tap **"Shop" ("Buy it here")** → routed to the affiliate
  link → the reviewer **earns a commission**.
- There is **no browse-and-buy catalog**. "Products" exist only as the subject of
  reviews. "Shop" is an **action sheet on a review**, not a page.

This maps 1:1 to the backend `ReviewOut` (verdict, pros/cons, target/anti-target
audience, star_rating, `referral_redirect_url`) and the admin review-queue /
referral-link / commission / payout endpoints.

## Personas & surfaces

- **Reader (public, no login):** Landing, Search, Review detail, Categories,
  reviewer Profiles, Recent Reads / Bookmarks.
- **Reviewer:** Write-a-review flow (Reviewer Page steps 1–7), Reviewer Dashboard
  (earnings / insights / history / transfer / payouts), Ask/Question flow.
- **Seller:** Seller-review flow, Seller page.
- **Moderator (admin):** review queue, approve/reject, attach affiliate link.

## Architecture / conventions (follow existing patterns)

- Next 16 App Router. Server components fetch via `lib/api/client.ts` (`apiFetch`,
  token from httpOnly cookie via `lib/dal.ts`); client components use the BFF route
  `app/api/bff/[...path]`. **Read `node_modules/next/dist/docs` before using an
  unfamiliar Next API** (per AGENTS.md).
- Design tokens in `app/tokens/*.css`, bridged into Tailwind v4. Never hardcode hex.
- Icons: **`@phosphor-icons/react/dist/ssr`** (the design's icon set; SSR-safe). Added
  as a dependency for the whole site.
- Light-only, mobile-first; `lg:` desktop treatments.
- Public read endpoints (published reviews/products) are fetched server-side without a
  token. A public **feed endpoint that joins review+author+product** does not yet
  exist, so list surfaces use curated sample content isolated in one module until that
  endpoint lands (a later wave / small backend addition).

## The 4 reported issues (fixed first)

1. **Re-onboarding after login** — `verifyOtp` always redirected to `/onboarding`.
   Fixed: after verify it checks `/auth/me` interests; returning members → `/`, new
   accounts → `/onboarding`. ✅ done
2. **"Introducing bluntly.ph / Search or Ask" circle** — that's onboarding step 3/4;
   the "circle" is an empty gray placeholder. Fill with real preview art (or drop the
   empty steps) during the onboarding polish.
3. **"/" forces sign-in** — `app/page.tsx` redirected signed-out visitors to
   `/welcome`. Replace with the **public landing page**; login stays reachable from the
   header.
4. **Setup progress bar invisible** — thicken/announce `StepBar` and add a real loading
   state on final submit.

## Build waves (breadth-first)

- **Wave 1 — App shell + Landing (public).** Site header, footer, bottom app nav,
  Review card, the public landing at `/`, `/search` stub. _(in progress)_
- **Wave 2 — Read surfaces.** Review detail page (+ "Buy it here" sheet), Search
  results, Categories/Subcategory, Recent Reads, Bookmarks.
- **Wave 3 — Reviewer write flow.** Reviewer Page steps 1–7 (find product → details →
  pros/cons → verdict → submit for moderation).
- **Wave 4 — Reviewer dashboard.** Earnings, insights, history, transfer, wallet/payouts.
- **Wave 5 — Seller + Q&A + Requests.** Seller-review flow, seller page, question pages,
  review requests/bounties.
- **Wave 6 — Profile + Moderation + polish.** Profile (stats/reviews/comments), admin
  review queue, onboarding art, data-wiring pass, accessibility + responsive audit.

## Open items

- Public **feed** endpoint (review + author + product) for list surfaces.
- Remote image config (`next.config` `images`) when wiring real review photos.
- `email_otps` RLS advisory (owner decision; backend uses direct DB, not the anon key).
