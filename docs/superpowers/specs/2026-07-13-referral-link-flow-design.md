# Referral Link Flow — Design Spec (M2 slice 1, publication-gated)

**Date:** 2026-07-13 (rev 2 — publication gate added per product owner) ·
**Status:** Finalized for implementation · **Planned on:** Fable 5 ·
**To be implemented on:** Opus 4.8 (model policy).

## Product decision (supersedes capstone FR-3 "publish immediately")

A user's review is **not public when submitted**. It waits in the moderator queue;
the moderator generates the referral link in their own affiliate dashboard (using
the product link the user posted) and pastes it here — **the act of pasting the
link is what publishes the post**. Reviews that can't carry a link (≤2★ honesty-fund
routing, non-monetizable platform) are published by an explicit moderator
publish action instead. **No scraping, no marketplace API calls** — the manual paste
is the compliance mechanism. Optimize everything for one moderator working fast.

## 1. State machine

Two orthogonal fields on `reviews`:
- **`published_at`** (new, nullable timestamptz) — `NULL` = hidden from public;
  set = live. Authors and moderators can always see their own/all reviews.
- **`earn_eligible_status`** (existing enum) — monetization state.

```
 submit review (with product link)
        │        review.published_at = NULL  (hidden)
        ▼        earn_eligible_status = pending  (auto — every new review queues)
 ┌─ MODERATOR QUEUE ─────────────────────────────────────────────┐
 │ One card = review text + stars + author + product.source_url  │
 │ (clickable) + platform + [paste referral link] [publish       │
 │ w/o link] [reject]                                            │
 └───────┬───────────────────────┬──────────────────┬────────────┘
         ▼ paste link (★≥3)      ▼ publish w/o link ▼ reject (reason)
   status=monetized         status=honesty_fund     status=rejected
   published_at=now()        (★≤2) or approved      stays hidden;
   → LIVE with link          (non-monetizable)      author may edit
                             published_at=now()     → back to pending
                             → LIVE, no link
```

- **Attach-and-publish is one action** — pasting a valid link both monetizes and
  publishes atomically (single transaction).
- **Revoke:** revoking a link does **not** unpublish (the content was approved);
  status returns to `approved`, link history kept. A separate moderator
  `unpublish` action exists for content that must come down (`published_at = NULL`,
  audit-logged) — distinct from `is_removed` (policy removal).
- **Edited-after-published:** an edit does not unpublish or auto-revoke; the queue
  flags *"edited since monetized"* (compare `reviews.current_version` to
  `referral_links.review_version`) for manual re-check.

## 2. Schema changes (one Alembic migration)

1. **`reviews.published_at`** timestamptz NULL. Backfill: existing reviews get
   `published_at = created_at` (they were created under publish-immediately — don't
   hide live content retroactively).
2. **New table `referral_links`** (history + audit; `reviews.affiliate_link` stays
   as the active-link mirror): `id` PK · `review_id` FK CASCADE · `platform` ·
   `url` · `status` enum `referral_link_status` (`active`|`revoked`) ·
   `review_version` int · `created_by` FK users SET NULL · `revoked_by`,
   `revoked_at`, `revoke_reason` · timestamps · **partial unique**
   `UNIQUE (review_id) WHERE status='active'` · RLS enabled (public SELECT).
3. **`ALTER TYPE platform ADD VALUE 'amazon'`** (M2). Must run in an
   `op.get_context().autocommit_block()` (Postgres: ADD VALUE can't run in the
   migration transaction).
4. **`ALTER TYPE moderation_action ADD VALUE`** ×4: `affiliate_link_attach`,
   `affiliate_link_revoke`, `publish`, `unpublish` (same autocommit caveat).
   Earn-eligible decisions reuse existing `approve`/`reject`.
5. Downgrade: drop table/column; enum values can't be dropped (documented).

## 3. Endpoints (`/api/v1`, RFC 9457 errors, existing RBAC)

### Public / author
| Endpoint | Behavior change |
|---|---|
| `GET /reviews`, `GET /reviews/{id}` | **Only `published_at IS NOT NULL`** for anonymous/other users; authors see their own unpublished (with status), moderators see all (`?include_unpublished=true`). |
| `POST /reviews` | Unchanged shape; response includes `published_at: null` + `earn_eligible_status: pending` — the frontend shows "awaiting moderator review". Product aggregates count **published** reviews only. |
| `GET /r/{review_id}` | Public attribution redirect (root-mounted, no auth): review must be published + monetized w/ active link → create `sessions` click row (click_ref, destination_url, platform, UA/IP with M0 retention deadlines via `services/pii`) → 302. Else 404 problem+json. `ReviewOut` exposes only this redirect URL, never the raw affiliate URL. |

### Moderator (all RBAC `moderator`, all audit-logged to `moderation_logs`)
| Endpoint | Purpose |
|---|---|
| `GET /admin/review-queue` | **The one queue.** Unpublished `pending` reviews, oldest first, each card carrying: review fields, `star_rating`, author (+trust fields), product (`canonical_name`, **`source_url`**, platforms + `is_monetizable`), and `suggested_platform`. Also returns a second list: monetized reviews *edited since monetized*. |
| `POST /admin/reviews/{id}/referral-link` | **Paste-and-publish**: body `{url, platform}` → validate (§4) → active `referral_links` row + mirror → `monetized` + `published_at=now()` in one transaction → audit `affiliate_link_attach`. 409 if already has an active link; 422 on validation failure; 409 if `star_rating ≤ 2` (must use publish-without-link → honesty fund). |
| `POST /admin/reviews/{id}/publish` | Publish **without** a link: `★≤2` → `honesty_fund`; else → `approved` (unmonetized, e.g. non-monetizable platform). Sets `published_at`; audit `publish`. |
| `POST /admin/reviews/{id}/reject` | Body `{reason}` (required). Status `rejected`, stays hidden; author edit resubmits → `pending`. Audit `reject`. |
| `DELETE /admin/reviews/{id}/referral-link` | Revoke active link (reason required); stays published, status → `approved`; audit `affiliate_link_revoke`. |
| `POST /admin/reviews/{id}/unpublish` | Takes content off the public site (`published_at=NULL`), independent of link state; audit `unpublish`. |
| `GET /reviews/{id}/referral-links` | Link history. |

**Moderator-speed requirements:** the queue payload must be complete enough that
the moderator never needs a second request per item (single card = read → click
`source_url` → generate in dashboard → paste → done). Support `?limit/offset`
and stable ordering so keyboard-driven UIs can walk the queue.

## 4. URL validation (pinned, config-driven)

`AFFILIATE_ALLOWED_DOMAINS` (env, per-platform), defaults:
`shopee: s.shopee.ph, shope.ee, shopee.ph` · `lazada: s.lazada.com.ph,
c.lazada.com.ph, lazada.com.ph` · `amazon: amzn.to, amazon.com, www.amazon.com`.
Rules: `https` only · host equals/subdomain of an allowed domain for the declared
platform · no userinfo · length ≤ 2048 · reject when the product's
`product_platforms.is_monetizable=false` for that platform (Lazada A6 guard).
Failures → 422 `affiliate_url_invalid` naming the failed rule.

## 5. Service boundary

`app/services/referral_service.py` — the `MarketplaceIntegrationService` seam:
`attach_link_and_publish`, `publish_without_link`, `reject`, `revoke_link`,
`unpublish`, `record_click`, `validate_affiliate_url`, `get_queue`. A future
marketplace API partnership changes only this module's internals.

## 6. Tests (required)

- Unit: URL validation matrix; transition guards (paste on ≤2★ → 409; double
  active link → 409; publish/reject on already-published → 409).
- Integration: **submit → hidden from public list → visible to author →
  queue shows card with source_url → paste(4★) → published+monetized →
  `GET /r/{id}` 302 + sessions row → revoke (stays published) → re-attach**;
  ≤2★ publish-without-link → honesty_fund + published; reject → hidden, edit
  resubmits; unpublish hides; aggregates count published only; RBAC 403s;
  edited-since-monetized flag appears.
- Regression: M1 tests updated for the publication gate (existing tests that
  assume immediate visibility must assert the new behavior instead).

## 7. Docs to update after build (checklist for the implementing session)

- [ ] `MARKETPLACE_INTEGRATION.md` §2 → as-built endpoints
- [ ] `backend/API_TESTING.md` → "Referral link flow" curl walkthrough
- [ ] `docs/schema.md` (+1 table, new column/enums) · `docs/DEVIATIONS.md`
      (**publication gate supersedes FR-3 publish-immediately**)
- [ ] `docs/openapi.json` re-export · full suite + live verification
- [ ] Migration applied to **both** local and Supabase (session pooler)

## 8. Out of scope for this slice

Wilson gate / effective-n voting · notifications (flag: author should eventually be
notified on publish/reject — no notification system yet) · CSV reconciliation ·
token economy · automated link generation · frontend.
