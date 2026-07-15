# Bluntly.ph — Data Dictionary (as migrated, M0)

15 tables, UUID primary keys (`gen_random_uuid()`) + human-readable ID strings,
timestamps via `created_at`/`updated_at`. Source of truth: `backend/app/models/`,
migrated by `backend/alembic/versions/`. This reflects the schema **as actually
migrated**; deviations from the original Data Dictionary are in
[`DEVIATIONS.md`](./DEVIATIONS.md).

## Enum types (`app/models/enums.py`)
`member_role`(user/seller/moderator) · `member_type`(shopper/seller/moderator) ·
`language`(en/fil/tl-x-taglish) · `product_status`(pending/canonicalized/rejected) ·
`platform`(shopee/lazada/other) · `verdict`(yes_absolutely/it_depends/hard_pass) ·
`verification_status`(verified/unverified) · `verification_tier`(tier_0/tier_1) ·
`earn_eligible_status`(none/pending/approved/rejected/monetized/honesty_fund) ·
`question_directed_to`(buyers/seller) · `conversion_status`(clicked/converted/cancelled) ·
`commission_target`(review/answer) · `moderation_target_type` · `moderation_action`
(incl. audit actions csv_import/payout/honesty_fund_distribution) · `moderation_reason` ·
`vote_direction`(up/down).

## Tables

| # | Table | Purpose | Key columns / notes |
|---|---|---|---|
| 1 | `users` | Profile keyed to Supabase `auth.users.id` | `id`(=JWT sub, PK, no auto-gen), `role`, `member_type`, `language`, `reputation_score`(0–100), `trust_stage`, **`trust_level_name`** (GENERATED ALWAYS), aggregates, `wallet_balance`, `payout_account`(sensitive). **No `password_hash`** (ADR-008). No `share_percentage` (removed). |
| 2 | `badges` | Badge definitions | `badge_id`, `name`, `criteria`(JSONB) |
| 3 | `user_badges` | Awarded badges | FK users/badges CASCADE, `uq(user_id,badge_id)` |
| 4 | `products` | Canonical products | `status`(pending→canonicalized), `source_url`, canonical name parts, denormalized `avg_rating`/`review_count`/`aggregated_pros/cons`(JSONB) |
| 5 | `product_platforms` | Per-platform listing | `platform`, `platform_url`, `is_monetizable`(Lazada A6), `uq(product,platform,url)` |
| 6 | `price_history` | Community price observations | `platform`, `price`, `variant`, `observed_at`, `submitted_by`. Never scraped. |
| 7 | `reviews` | Structured reviews | `verdict`, `star_rating`, `pros/cons`(JSONB), `photo_url`, `receipt_url`, `verification_status`, `verification_tier`, `wilson_score`, `earn_eligible_status`, `affiliate_link` |
| 8 | `questions` | Q&A questions | `directed_to`, `best_answer_id`(deferred FK, use_alter) |
| 9 | `answers` | Q&A answers | `is_best_answer`, `is_first_responder`, `wilson_score`, **`earn_eligible`(unwired, ADR-006)** |
| 10 | `seller_reviews` | 4-dimension seller reviews | `accuracy`, `order_completeness`(binary), `customer_service`, `packaging_quality`, `overall_rating`, `would_recommend` |
| 11 | `sessions` | Affiliate click tracking + PII lifecycle | `click_ref`/`order_ref`, `conversion_status`, `user_agent`, `ip_address`, `ip_hash`, precomputed `ua_purge_at`/`ip_hash_at`/`ip_delete_at` |
| 12 | `commissions` | Reconciled commissions | `target_type`+typed `review_id`/`answer_id` FKs (CHECK), 40/30/30 shares, `uq(csv_source,row_reference)` (idempotency) |
| 13 | `honesty_fund_distributions` | Monthly HF payouts | `cycle_month`, `honesty_score`, `pool_amount`, `payout_amount`, `uq(cycle_month,review_id)` |
| 14 | `moderation_logs` | Moderation **+ audit log** | polymorphic `target_type`/`target_ref`, `action`, `reason`, `context`(JSONB) |
| 15 | `earn_eligible_votes` | Gate votes w/ immutable snapshots | `vote_weight`, `trust_stage_snapshot`, `trust_score_snapshot`, `account_age_days_snapshot`, `is_probation_snapshot`, `uq(review_id,voter_id)` |

## M1 additions (schema grew 15 → 17 tables)

| # | Table | Purpose | Key columns |
|---|---|---|---|
| 16 | `membership_tiers` | Tier config (ADR-012) | `code`(special/founding/standard, unique), `name`, `revenue_share_bps`, `payout_priority`, `benefits`(JSONB), `is_active` |
| 17 | `review_versions` | Review edit history | `review_id`(FK CASCADE), `version_number`, `snapshot`(JSONB), `edited_by`, `change_note`, `uq(review_id,version_number)` |

New columns (M1): `users.password_hash` (Argon2id, ADR-011), `users.is_suspended`,
`users.membership_tier` (enum, default standard, ADR-012); `reviews.current_version`.
`users.id` gains a `gen_random_uuid()` default (ADR-010, no longer the Supabase uid).

## M2 slice-1 additions (referral link flow — 18 → 19 tables)

| # | Table | Purpose | Key columns |
|---|---|---|---|
| 19 | `referral_links` | Affiliate link history + audit | `review_id`(FK CASCADE), `platform`, `url`, `status`(referral_link_status active/revoked), `review_version`, `created_by`, `revoked_by`/`revoked_at`/`revoke_reason`. Partial unique `UNIQUE(review_id) WHERE status='active'` (one active link per review). RLS on (public SELECT). |

New enum type `referral_link_status`(active/revoked). `platform` gains **`amazon`**;
`moderation_action` gains `affiliate_link_attach`, `affiliate_link_revoke`,
`publish`, `unpublish`. New column **`reviews.published_at`** (nullable; publication
gate — NULL = hidden). `reviews.affiliate_link` is the active-link mirror; the raw
value is never exposed in API responses (only the `/r/{id}` redirect is).

## M2 slices 2–8 additions (19 → 21 tables; migrations 0005–0009)

| # | Table | Purpose | Key columns |
|---|---|---|---|
| 20 | `review_votes` | Equal-weight community visibility votes (slice 2) | `review_id`(FK CASCADE), `voter_id`(FK CASCADE), `vote`(vote_direction), `uq(review_id,voter_id)` — one vote per user per review, changing = upsert. RLS on (public SELECT). |
| 21 | `token_transactions` | Append-only token ledger (slice 7) | `user_id`(FK CASCADE), `amount`(±, CHECK ≠0), `balance_after`, `kind`(token_kind), polymorphic `ref_type`/`ref_id`, `note`, `created_by`. Index `(user_id, created_at DESC)`. Partial unique `uq_token_once(user_id,kind,ref_id) WHERE ref_id IS NOT NULL AND kind LIKE 'earn_%'` (a review/commission awards once). RLS on with **no permissive policy** (like `sessions`). |

New enum type `token_kind`(earn_review_published/earn_commission/admin_grant/
admin_deduct/adjustment). New columns: **`products.trust_score`** Numeric(6,5)
(time-decayed Wilson over published reviews with stars ≥ 4, slice 4);
**`users.seller_trust_score`** Numeric(6,5) NULL + per-dimension aggregates in the
existing `users.seller_aggregates` JSONB (slice 4); **`users.token_balance`** int
(ledger mirror, slice 7); **`commissions.reviewer_tier`** + 
**`commissions.reviewer_share_bps`** (immutable tier snapshot at reconciliation,
slice 6). New constraint `uq_seller_review_once(seller_id, reviewer_id)` on
`seller_reviews` (slice 4). Extension **`pg_trgm`** + GIN index
`ix_reviews_discussion_trgm` on `reviews.discussion` (duplicate-content signal,
slice 5).

## Row-Level Security
All 15 tables have RLS enabled (31 policies). Owner-write tables key on
`auth.uid()`; public-read on content/reference tables; admin-only tables
(`sessions`, `commissions`, `honesty_fund_distributions`, `moderation_logs`) have
no permissive policy (service-role only). See `alembic/versions/0002_rls_policies.py`.
