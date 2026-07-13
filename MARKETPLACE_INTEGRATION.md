# Marketplace Integration — Manual Admin Workflows

> For the human platform administrator who operates Bluntly.ph. **Non-negotiable
> constraint:** Shopee and Lazada ToS prohibit automated data extraction. There is
> **no scraping, no unofficial API client, and no headless-browser ingestion**
> anywhere in this system — not for staging, not to save time. Every marketplace
> touchpoint below is admin-mediated by design.

## Status note (updated 2026-07-13)
M0 laid the **schema, service boundary, and constraint**. Delivery then moved to the
product owner's milestones (`docs/MILESTONES.md`): **M1 (done)** shipped auth,
reviews + version history, tiers, and AI critique — products are currently created
directly (the pending→canonicalized admin queue in §1 is **not yet built**). The
**referral/affiliate link flow (§2) is now fully specified** in
`docs/superpowers/specs/2026-07-13-referral-link-flow-design.md` and is the first
M2 implementation slice. CSV reconciliation (§3) remains a later M2 slice.

The swappable boundary is a `MarketplaceIntegrationService` seam — first realized as
`app/services/referral_service.py` (per the spec): if a formal marketplace API
partnership is ever signed, the manual steps below become automated calls behind the
*same* interface — the review / earning / reconciliation logic downstream does not
change.

## 1. Product canonicalization (§3.1)
1. A user submits a product by pasting a Shopee/Lazada URL → stored on `products` as
   `source_url` with `status = pending`. **The app never fetches that URL.**
2. The admin queue lists pending submissions (raw URL + any user title/photo).
3. The admin manually sets the canonical name (**Brand · Line · Key Spec ·
   Descriptor**), category, and links/creates the `products` + `product_platforms`
   rows, flipping `status → canonicalized`.
4. **Assistive only:** trigram/`pg_trgm` fuzzy suggestions against existing
   `products.canonical_name` speed the admin's decision. This is UI assistance, not
   ingestion — it touches only our own DB, never Shopee/Lazada.

## 2. Referral / affiliate link attachment (§3.2) — ✅ BUILT (2026-07-13), publication-gated
> As-built endpoints (all moderator, under `/api/v1/admin`):
> `GET /review-queue` · `POST|DELETE /reviews/{id}/referral-link` (attach / revoke) ·
> `POST /reviews/{id}/publish` (no-link) · `POST /reviews/{id}/reject` ·
> `POST /reviews/{id}/unpublish` · `GET /reviews/{id}/referral-links` (history).
> Public attribution: `GET /r/{review_id}` (302 + click session). Service:
> `app/services/referral_service.py`. Spec:
> `docs/superpowers/specs/2026-07-13-referral-link-flow-design.md`. Summary:

1. **A new review is NOT public when submitted** (`published_at = NULL`; supersedes
   the capstone's publish-immediately rule). It auto-enters the moderator queue.
2. **One queue card = everything the moderator needs**: review text + stars +
   author + the product link the user posted (`source_url`, clickable) + a paste
   box. Workflow: read → open the user's link → generate the referral link in your
   **own logged-in affiliate dashboard** (Shopee / Lazada / Amazon — outside this
   app) → paste it.
3. **Pasting the link publishes the post** — one atomic action
   (`POST /admin/reviews/{id}/referral-link`): validate (https, config-allowlisted
   domain per platform, no userinfo, monetizable platform) → `referral_links`
   history row (one active per review, `reviews.affiliate_link` mirror) →
   `earn_eligible_status = monetized` + `published_at = now()` → live. Audit-logged.
4. **No-link publish path:** ≤ 2★ reviews (Honesty Fund) and non-monetizable
   platforms are published via an explicit publish action instead — live without a
   link. Reject (reason required) keeps the post hidden; the author may edit and
   resubmit.
5. **Attribution:** the public review exposes only the redirect `GET /r/{review_id}`
   (records a `sessions` click row under the PII retention schedule, then 302s) —
   never the raw affiliate URL.
6. **Revocation** keeps the post published but drops it back to "link pending";
   history is kept. Edits after publish don't auto-revoke — the queue flags
   *"edited since monetized"* for manual re-check. A separate unpublish action
   takes content down.
7. **Lazada (A6, unresolved):** do **not** assume a Lazada affiliate program exists.
   Lazada products carry `product_platforms.is_monetizable = false` until confirmed;
   they can still be listed and reviewed — link attach is rejected for
   non-monetizable platforms.

## 3. Commission reconciliation (§3.3)
1. The admin exports commission CSVs **manually** from the Shopee Affiliate dashboard
   and Lazada portal.
2. The admin uploads each CSV via an authenticated admin endpoint.
3. The backend parses/validates the CSV (rejecting malformed rows with a clear error
   report — no silent partial success), matches rows to `sessions` via
   `click_ref`/`order_ref`, and writes `commissions` with the **40/30/30** shares +
   `csv_source`/`row_reference`.
4. **Idempotent:** `uq(csv_source, row_reference)` means re-uploading the same CSV
   cannot double-count. Large files reconcile in a **Celery task**
   (`reconcile_commission_csv`); progress/errors surface back to the admin. Every
   import is logged in `moderation_logs` (audit action `csv_import`).

## 4. Price observations (§3.4)
Prices come **only** from user submissions (`price_history`: platform, price, date,
variant) — never fetched from a marketplace. The price panel shows only when **≥ 3
independent observations** exist.

## If the manual workflow feels slow
Do **not** add a "just in case" scraper or unofficial API client. Flag the friction
on the admin review card and let a human resolve it. The manual design is the
compliance mechanism, not a stopgap.
