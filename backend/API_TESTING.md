# API Testing Guide — Bluntly.ph Backend (M1)

How to exercise every M1 endpoint. Base URL assumes the local stack on
`http://localhost:8000`. All error responses are RFC 9457 `application/problem+json`.

## 0. Prerequisites

```bash
cd backend
docker compose up -d --build     # postgres, redis, api (runs migrations), worker, beat
curl -s http://localhost:8000/health   # {"status":"ok","product_id":"bluntly-ph",...}
```

Seed sample data (tiers, badges, sample products) once:

```bash
docker compose exec api python -m scripts.seed
```

> **Windows PowerShell:** use `curl.exe` (PowerShell's `curl` is an alias for
> `Invoke-WebRequest`). The examples below are shown for bash/Git Bash. For form
> logins in PowerShell, see the note in §3.

### Easiest: interactive Swagger UI
Open **http://localhost:8000/docs** — try every endpoint in the browser, use
"Authorize" to paste a Bearer token. (`/redoc` and `/openapi.json` are also served;
all three are hidden when `ENABLE_DOCS=false`.)

---

## 1. Health (no auth)

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","product_id":"bluntly-ph","version":"0.1.0","timestamp":"..."}`

---

## 2. Register  (`POST /api/v1/auth/register`)

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"password123","display_name":"Alice"}'
```

Returns `201` with `{access_token, token_type, expires_in, user}`. `user.membership_tier`
is `standard`. Save the token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"password123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
```

- **Duplicate email** → `409` `{"code":"email_taken",...}`
- **Password < 8 chars** → `422` validation problem.

---

## 3. Login  (`POST /api/v1/auth/login`, OAuth2 password form)

Login uses **form-encoded** fields `username` (= email) and `password`, not JSON:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d 'username=alice@example.com&password=password123'
```

Returns `200` with the same token payload. Wrong password → `401`
`{"code":"invalid_credentials"}`.

> **PowerShell:** `curl.exe -s -X POST http://localhost:8000/api/v1/auth/login -d "username=alice@example.com&password=password123"`

---

## 4. Current user  (`GET /api/v1/auth/me`)

```bash
curl -s http://localhost:8000/api/v1/auth/me -H "$AUTH"
```

No/invalid token → `401` `{"code":"unauthorized"}` / `{"code":"token_invalid"}`.

---

## 5. Products  (support reviews)

```bash
# Create
PID=$(curl -s -X POST http://localhost:8000/api/v1/products -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Aukey 10000mAh Power Bank","category":"electronics"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -s http://localhost:8000/api/v1/products                # list
curl -s http://localhost:8000/api/v1/products/$PID           # get one
```

---

## 6. Reviews + version history

```bash
# Create (photo_url => verified; omit it => unverified)
RID=$(curl -s -X POST http://localhost:8000/api/v1/reviews -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{
    \"product_id\":\"$PID\",\"title\":\"Solid daily driver\",
    \"discussion\":\"Charged my phone 3x on one charge. Fast, but bulky.\",
    \"verdict\":\"yes_absolutely\",\"star_rating\":4,
    \"pros\":[\"fast charging\"],\"cons\":[\"bulky\"],
    \"photo_url\":\"https://example.com/proof.jpg\"}" \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Edit -> creates version 2 (any changed field bumps current_version)
curl -s -X PATCH http://localhost:8000/api/v1/reviews/$RID -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Solid daily driver (updated)","change_note":"clarified title"}'

# List / get / versions
curl -s "http://localhost:8000/api/v1/reviews?product_id=$PID"   # filter by product
curl -s http://localhost:8000/api/v1/reviews/$RID
curl -s http://localhost:8000/api/v1/reviews/$RID/versions       # [{version_number:1,...},{2,...}]
curl -s http://localhost:8000/api/v1/reviews/$RID/versions/1     # original snapshot
```

`verdict` ∈ `yes_absolutely | it_depends | hard_pass`; `star_rating` 1–5; `pros`/`cons`
≤ 10 items. **Editing someone else's review** (a different user's token) → `403`
`{"code":"not_review_owner"}`.

---

## 7. AI critique

Default provider is **`stub`** (deterministic, no API key needed):

```bash
# Critique a stored review
curl -s -X POST http://localhost:8000/api/v1/reviews/$RID/critique -H "$AUTH"

# Ad-hoc critique of arbitrary draft text
curl -s -X POST http://localhost:8000/api/v1/ai/critique -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Draft","text":"Short but honest. Pro: cheap. Con: loud."}'
```

Returns `{provider, model, quality_score, summary, strengths[], weaknesses[], suggestions[]}`.

**Enable real Claude critique:** set `AI_PROVIDER=claude` and `ANTHROPIC_API_KEY=...`
in `.env` (optionally `AI_MODEL=claude-opus-4-8`), then `docker compose up -d`.
Without a key while `AI_PROVIDER=claude` → `503` `{"code":"ai_not_configured"}`.

---

## 8. Membership tiers

```bash
curl -s http://localhost:8000/api/v1/membership-tiers            # public list
curl -s http://localhost:8000/api/v1/membership-tiers/founding   # one tier
```

### Moderator-only actions
RBAC reads the **DB role**, not the token — so to test moderator endpoints, promote a
user to `moderator` in the DB; their existing token then works (no re-login needed):

```bash
# Promote bob to moderator
docker compose exec postgres psql -U bluntly \
  -c "UPDATE users SET role='moderator' WHERE email='bob@example.com';"

# Update a tier's config (moderator)
curl -s -X PATCH http://localhost:8000/api/v1/membership-tiers/standard -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"revenue_share_bps":3200}'

# Assign a tier to a user (moderator). USER_ID = target user's UUID.
curl -s -X PATCH http://localhost:8000/api/v1/users/$USER_ID/membership-tier -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"membership_tier":"founding"}'
```

A non-moderator calling these → `403` `{"code":"role_forbidden"}`.

---

## 8b. Referral link flow + publication gate (M2)

**A new review is hidden** (`published_at: null`, `earn_eligible_status: pending`)
until a moderator publishes it. Pasting a referral link both monetizes **and**
publishes. Assume `$AUTH` = author token, `$MH` = a moderator's auth header (see §8
to promote a user).

```bash
# Author submits a verified review (>=3 stars, with a proof photo)
PID=$(curl -s -X POST http://localhost:8000/api/v1/products -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"BT Earphones","source_url":"https://shopee.ph/x-i.1.2"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
RID=$(curl -s -X POST http://localhost:8000/api/v1/reviews -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"product_id\":\"$PID\",
    \"title\":\"Great\",\"discussion\":\"Used for weeks.\",\"verdict\":\"yes_absolutely\",
    \"star_rating\":5,\"photo_url\":\"https://example.com/proof.jpg\"}" \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Hidden from the public list; the author still sees their own draft
curl -s http://localhost:8000/api/v1/reviews            # $RID absent
curl -s http://localhost:8000/api/v1/reviews -H "$AUTH" # $RID present

# Moderator queue — one card carries the product link + a suggested platform
curl -s http://localhost:8000/api/v1/admin/review-queue -H "$MH"

# Paste the referral link -> monetize + publish (one action)
curl -s -X POST http://localhost:8000/api/v1/admin/reviews/$RID/referral-link -H "$MH" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://shopee.ph/x-i.1.2?af=abc","platform":"shopee"}'
# -> earn_eligible_status: monetized, published_at set, referral_redirect_url: /r/<id>

# Public attribution redirect (records a click session, then 302s)
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" http://localhost:8000/r/$RID

# Other moderator actions
curl -s -X POST http://localhost:8000/api/v1/admin/reviews/$RID/publish   -H "$MH"      # <=2* / no-link -> Honesty Fund
curl -s -X POST http://localhost:8000/api/v1/admin/reviews/$RID/reject    -H "$MH" -d '{"reason":"blurry proof"}' -H 'Content-Type: application/json'
curl -s -X DELETE http://localhost:8000/api/v1/admin/reviews/$RID/referral-link -H "$MH" -d '{"reason":"expired"}' -H 'Content-Type: application/json'
curl -s -X POST http://localhost:8000/api/v1/admin/reviews/$RID/unpublish -H "$MH" -d '{}' -H 'Content-Type: application/json'
curl -s http://localhost:8000/api/v1/admin/reviews/$RID/referral-links -H "$MH"          # link history
```

Guards: attach on a ≤2★ review → `409 stars_too_low_for_link`; on an unverified
review → `409 review_not_verified`; a bad URL (http, wrong domain, wrong platform)
→ `422 affiliate_url_invalid` (with the failed `rule`). Editing a monetized review
surfaces it under `edited_since_monetized` in the queue for re-check.

## 8c. M2 — voting, trust, sellers, fraud signals, commissions, tokens, Honesty Fund

```bash
# --- Community voting (published reviews only; no self-votes) ---
curl -s -X POST http://localhost:8000/api/v1/reviews/$RID/vote -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"vote":"up"}'     # or "down"; re-POST = change
curl -s -X DELETE http://localhost:8000/api/v1/reviews/$RID/vote -H "$AUTH"
curl -s "http://localhost:8000/api/v1/reviews?sort=wilson"   # Wilson-ranked listing

# --- Trust profile (public) ---
curl -s http://localhost:8000/api/v1/users/$USER_ID/trust
# -> {trust_stage, trust_level_name, reputation_score, verified_review_count,
#     helpfulness_ratio, badges:[{badge_id,name,awarded_at}]}

# --- Seller role + seller reviews ---
curl -s -X PATCH http://localhost:8000/api/v1/users/$USER_ID/role -H "$MH" \
  -H 'Content-Type: application/json' -d '{"role":"seller"}'   # moderator only; "moderator" -> 422
curl -s -X POST http://localhost:8000/api/v1/sellers/$SELLER_ID/reviews -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"accuracy":true,"order_completeness":true,
    "customer_service":5,"packaging_quality":4,"overall_rating":5,"would_recommend":true}'
curl -s http://localhost:8000/api/v1/sellers/$SELLER_ID          # profile + dimension averages
curl -s http://localhost:8000/api/v1/sellers/$SELLER_ID/reviews  # newest first

# --- Product trust & visibility thresholds ---
curl -s http://localhost:8000/api/v1/products                        # low-trust products excluded (if thresholds on)
curl -s "http://localhost:8000/api/v1/products?include_low_trust=true"
curl -s http://localhost:8000/api/v1/products/$PID                   # always retrievable; carries low_trust flag

# --- Fraud signals: moderator queue cards carry `signals` (advisory only) ---
curl -s http://localhost:8000/api/v1/admin/review-queue -H "$MH"
# item.signals = {velocity, collusion, duplicate_content, duplicate_of,
#                 author_account_age_days, author_review_count}

# --- Commission CSV import (moderator; all-or-nothing; idempotent) ---
cat > /tmp/commissions.csv << 'CSV'
click_ref,order_ref,gross_amount,currency,order_status,platform
ref_abc123,ORD-1,100.00,PHP,completed,shopee
CSV
curl -s -X POST http://localhost:8000/api/v1/admin/commissions/import -H "$MH" \
  -F "file=@/tmp/commissions.csv"
# -> {imported, skipped_duplicates, unmatched, total_rows}; any invalid row -> 422 errors:[{line,issue}]

# --- Tokens (append-only ledger; spending is M3) ---
curl -s http://localhost:8000/api/v1/tokens/balance -H "$AUTH"
curl -s "http://localhost:8000/api/v1/tokens/transactions?limit=50" -H "$AUTH"
curl -s -X POST http://localhost:8000/api/v1/admin/users/$USER_ID/tokens -H "$MH" \
  -H 'Content-Type: application/json' -d '{"amount":25,"note":"manual bonus"}'   # negative deducts

# --- Honesty Fund cycle (moderator; idempotent per cycle) ---
curl -s -X POST http://localhost:8000/api/v1/admin/honesty-fund/run -H "$MH" \
  -H 'Content-Type: application/json' -d '{"cycle_month":"2026-06"}'
# -> {cycle_month, pool, recipients, status: distributed|empty_pool|already_distributed|no_eligible_reviews}
```

Guards worth knowing: vote on own review → `409 cannot_vote_own_review`; vote on an
unpublished review → `404`; votes are rate-limited (`VOTE_RATE_LIMIT_MAX`/60s);
duplicate seller review → `409 seller_review_exists`; token deduct below zero →
`409 insufficient_tokens`; tier bps > 7000 at import → `422 tier_bps_invalid`.

## 9. Error contract & rate limiting

- Every error is `application/problem+json`:
  `{"type","title","status","detail","instance","code",...}`.
- Auth endpoints are rate-limited (default 10/min/IP); exceeding → `429`
  `{"code":"rate_limited","retry_after_seconds":N}`.
- Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440); expired →
  `401` `{"code":"token_expired"}`.

---

## 10. Testing against Supabase instead of local

The same endpoints work against Supabase — point the app at it and restart:

```bash
# In .env: USE_SUPABASE=true and SUPABASE_CONNECTION_STRING_SESSION_POOLER=...
python -m scripts.db_check      # verify reachability + public table count
uvicorn app.main:app --reload   # or run the container with those env vars
```

**Deep verification** (`scripts/supabase_verify.py`) goes further than reachability.
51 checks in three layers:

1. **Schema truth** — all 21 tables, M2 columns, partial-unique/trigram indexes,
   RLS state + policies, enum values, seeded tiers/badges.
2. **Whole-database integrity invariants** — hold for *every* row, not just this
   run's, so they catch drift a per-flow assertion can't see: every
   `users.token_balance` equals the sum of its ledger amounts; every
   `wallet_balance` equals its commission shares + fund payouts; no
   `(user, earn kind, ref)` awarded twice; no orphaned votes/tokens; no negative
   balances; every commission's three shares re-sum to `gross_amount`.
3. **Flow truth** — drives a full API flow in-process and asserts every side
   effect with direct SQL: review→publish→link→click→vote→trust→badge→CSV
   import→wallet/tokens→honesty fund→PII sweep. Cleans up after itself
   (`--keep` to leave the rows).

```bash
USE_SUPABASE=true python -m scripts.supabase_verify
# === RESULT: 51/51 passed ===
```

Green on **local and Supabase** as of 2026-07-15, and on a from-scratch database.

> **Historical note (resolved 2026-07-15).** Layer 2 once reported 9 test users
> with wallet drift (PHP 54.00) and 12 arithmetically impossible `com_test_*`
> commissions. Both were **test-tooling artifacts, never app defects**: an older
> `supabase_verify` cleanup deleted a fund cycle's distribution rows without
> reversing the wallet credits `distribute()` had made to other pre-existing test
> reviews, and the old `_seed_pool` fixture inserted `gross=100` with `30+30+30`
> shares. All three are fixed — the cleanup now reverses credits before deleting,
> `_seed_pool` uses `split_commission()`, and both databases were reconciled to
> their source-of-truth rows. Kept here because the invariants in layer 2 exist
> precisely to catch this class of drift, and they did.

See `../docs/PRODUCTION.md` for the full production runbook.

---

## 11. Automated tests

The pytest suite covers all of the above (auth flow, review versioning, ownership
enforcement, tiers/RBAC, AI stub, plus the M0 trust/Wilson/PII math):

```bash
cd backend
pytest -q                 # full suite (needs Postgres on localhost:5432)
SKIP_DB_TESTS=1 pytest -q  # pure-logic + API-contract tests only
```
