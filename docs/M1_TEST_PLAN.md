# Milestone 1 — Acceptance Test Plan (run independently)

**Scope:** M1 Core System — accounts/auth, membership tiers, review submission +
version history, AI critique. A tester can execute this end-to-end against a running
backend without the dev team. Fill in the **Result** column (PASS / FAIL) and Notes.

- **Tester:** ______________  **Date:** __________  **Build/commit:** __________
- **Run this plan against BOTH environments** (tick each when complete):
  ☐ **Local** (`http://localhost:8000`)  ☐ **Supabase-backed** (see §0b — **required**)

---

## 0. Setup (do this once)

**Pick how you'll drive the API:**

- **Swagger UI (easiest):** open `‹BASE_URL›/docs`. Use the green **Authorize**
  button to paste a token (see below), then "Try it out" on each endpoint.
- **curl / Postman:** examples below. Set `BASE=‹BASE_URL›` (e.g.
  `export BASE=http://localhost:8000`).

**If testing locally**, start the stack first:
```bash
cd backend && docker compose up -d --build
curl -s $BASE/health          # expect {"status":"ok",...}
```

**Get a normal-user token** (used for most tests):
```bash
curl -s -X POST $BASE/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"tester1@example.com","password":"password123","display_name":"Tester One"}'
# copy the "access_token" from the response
export TOKEN=<paste access_token>
```

**Get a MODERATOR token** (needed for Group B tier-management tests). M1 has no
self-serve role change, so an admin promotes the account in the DB **once**; the
same token then works (roles are read from the DB):
```bash
# register a second user (e.g. modtester@example.com), then an admin runs ONE of:
#   local docker:   docker exec backend-postgres-1 psql -U bluntly -c "UPDATE users SET role='moderator' WHERE email='modtester@example.com';"
#   Supabase:       run the same UPDATE in the Supabase SQL editor
export MODTOKEN=<that user's access_token>
```

> **⚠️ Important — publication gate:** since a later change, a submitted review is
> **not public until a moderator publishes it** (that's the M2 referral flow, out of
> M1 scope). For M1 review tests, that means a freshly submitted review shows
> `published_at: null` and `earn_eligible_status: "pending"`, and the **author can
> still see and edit their own draft**. This is expected — note it, don't fail it.

---

## 0b. Testing against Supabase (REQUIRED)

Supabase is the **production database** — the app must behave identically there and
the data must actually persist in the Supabase project. Do a **full pass of Groups
A–E** against a Supabase-backed instance, not only local.

**Option 1 — a shared staging URL that's already Supabase-backed:** just set
`BASE` to that URL and run every group. Nothing else changes.

**Option 2 — run a Supabase-backed server yourself** (needs the repo + the Supabase
**session-pooler** connection string from the dashboard → Connect → *Session
pooler*):
```bash
# In the repo-root .env:  USE_SUPABASE=true
#                         SUPABASE_CONNECTION_STRING_SESSION_POOLER=<session pooler string>
cd backend
USE_SUPABASE=true python -m scripts.db_check           # expect: CONNECTED [ok], public tables: 19
USE_SUPABASE=true uvicorn app.main:app --port 8001     # Supabase-backed API
export BASE=http://localhost:8001                      # point all tests here
```
> Use the **session-pooler** string (host `aws-<n>-<region>.pooler.supabase.com`,
> IPv4). The **direct** host `db.<ref>.supabase.co` is IPv6-only and will fail to
> resolve on most networks.

**Moderator promotion on Supabase** — do it in the **Supabase Dashboard → SQL
Editor** (not `docker exec`):
```sql
UPDATE users SET role = 'moderator' WHERE email = 'modtester@example.com';
```

**Supabase-specific checks (in addition to Groups A–E):**

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| S1 | Connectivity | `USE_SUPABASE=true python -m scripts.db_check` (or hit `‹BASE›/health`) | `CONNECTED [ok]`, **19** public tables; `/health` = `200` | | |
| S2 | Data persists in Supabase | After A1/C1, open Dashboard → **Table Editor → schema `public`** | Your test `users` and `reviews` rows are visible in the `public` schema | | |
| S3 | Same behavior as local | Re-run Groups **A–E** with `BASE` = the Supabase instance | Every case passes exactly as it did locally | | |
| S4 | Schema is ours, not Storage | In the Dashboard schema dropdown | App tables are under **`public`**; the `storage.*` tables are Supabase's own — ignore them | | |

> **Heads-up:** this writes real rows (test users/reviews/sessions) into the Supabase
> project. That's expected for verification — delete them from the Table Editor
> afterward if you want a clean project.

---

## Group A — Accounts & Authentication (FR-1)

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| A1 | Register new account | `POST /api/v1/auth/register` `{email,password,display_name}` | `201`; body has `access_token` + `user`; `user.membership_tier` = `standard`, `role` = `user` | | |
| A2 | Duplicate email rejected | Register again with the **same** email | `409`; `code` = `email_taken` | | |
| A3 | Weak password rejected | Register with `password` shorter than 8 chars | `422` (validation problem+json) | | |
| A4 | Login (valid) | `POST /api/v1/auth/login` **form fields** `username`=email, `password` | `200`; returns a token | | |
| A5 | Login (wrong password) | Same, wrong password | `401`; `code` = `invalid_credentials` | | |
| A6 | Current user | `GET /api/v1/auth/me` with `Authorization: Bearer $TOKEN` | `200`; email matches; shows `membership_tier`, `role`, `trust_level_name` | | |
| A7 | Protected route needs auth | `GET /api/v1/auth/me` **without** a token | `401`; `code` = `unauthorized` | | |
| A8 | Language preference | Register with `"language":"tl-x-taglish"` (also try `en`, `fil`) | `201`; accepted (invalid values → `422`) | | |

> curl for A4/A5 (form-encoded, not JSON):
> `curl -s -X POST $BASE/api/v1/auth/login -d 'username=tester1@example.com&password=password123'`

---

## Group B — Membership Tiers (Special / Founding / Standard)

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| B1 | List tiers | `GET /api/v1/membership-tiers` | `200`; includes `special`, `founding`, `standard` with `revenue_share_bps`, `payout_priority` | | |
| B2 | Get one tier | `GET /api/v1/membership-tiers/founding` | `200`; the founding tier | | |
| B3 | New user default tier | Check A1's response / `GET /me` | `membership_tier` = `standard` | | |
| B4 | Non-moderator can't edit tier | `PATCH /api/v1/membership-tiers/standard` `{"revenue_share_bps":3100}` with `$TOKEN` | `403`; `code` = `role_forbidden` | | |
| B5 | Moderator edits tier config | Same PATCH with `$MODTOKEN` | `200`; value updated | | |
| B6 | Moderator assigns a user's tier | `PATCH /api/v1/users/‹USER_ID›/membership-tier` `{"membership_tier":"founding"}` with `$MODTOKEN` | `200`; user's tier changes. Same call with `$TOKEN` → `403` | | |

---

## Group C — Review Submission & Version History (FR-3)

First create a product to review:
```bash
export PID=$(curl -s -X POST $BASE/api/v1/products -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Test Power Bank","category":"electronics"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
```

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| C1 | Submit verified review | `POST /api/v1/reviews` with all required fields **and** `photo_url` (see body below) | `201`; `verification_status` = `verified`; `current_version` = 1; `published_at` = `null`; `earn_eligible_status` = `pending` | | |
| C2 | Submit unverified review | Same but **omit** `photo_url` | `201`; `verification_status` = `unverified` | | |
| C3 | Field validation | Submit with `star_rating` = 7, or `pros` list of 11 items, or bad `verdict` | `422` each time | | |
| C4 | Author edits review | `PATCH /api/v1/reviews/‹RID›` `{"title":"New title","change_note":"fix"}` with author token | `200`; `current_version` = 2 | | |
| C5 | No-op edit | PATCH again with the **same** title | `current_version` stays 2 (no empty version) | | |
| C6 | Only author/mod can edit | PATCH with a **different** user's token | `403`; `code` = `not_review_owner` | | |
| C7 | Version history | `GET /api/v1/reviews/‹RID›/versions` with author token | `200`; versions ordered `[1, 2]` | | |
| C8 | Specific version | `GET /api/v1/reviews/‹RID›/versions/1` with author token | `200`; snapshot shows the **original** title | | |
| C9 | Draft visibility | `GET /api/v1/reviews` **with** author token vs **without** any token | Author's list **includes** the draft; anonymous list **excludes** it | | |

> Review body for C1 (verified):
> ```json
> {"product_id":"‹PID›","title":"Solid daily driver","discussion":"Charged my phone 3x on one charge.",
>  "verdict":"yes_absolutely","star_rating":4,"pros":["fast charging"],"cons":["bulky"],
>  "photo_url":"https://example.com/proof.jpg"}
> ```
> `verdict` ∈ `yes_absolutely | it_depends | hard_pass`. Capture the returned `id` as `RID`.

---

## Group D — AI Critique

The default provider is a **deterministic stub** (no API key needed), so these work
out of the box. If the deployment set `AI_PROVIDER=claude`/`openai` with a key, the
critique text is model-generated instead.

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| D1 | Critique a stored review | `POST /api/v1/reviews/‹RID›/critique` with the **author** token | `200`; JSON with `provider`, `quality_score` (0–100), `summary`, `strengths[]`, `weaknesses[]`, `suggestions[]` | | |
| D2 | Ad-hoc critique of text | `POST /api/v1/ai/critique` `{"title":"Draft","text":"Short but honest. Con: loud."}` with a token | `200`; same shape | | |
| D3 | Critique needs auth | `POST /api/v1/ai/critique` **without** a token | `401` | | |
| D4 | Critique ownership | Critique someone else's review with a non-author, non-moderator token | `403`; `code` = `not_review_owner` | | |
| D5 | Provider-not-configured (only if `AI_PROVIDER=claude/openai` and no key) | Trigger any critique | `503`; `code` = `ai_not_configured` | | N/A if provider = stub |

---

## Group E — Cross-cutting

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| E1 | Error format | Trigger any error (e.g. A7) | Response is `application/problem+json` with `type,title,status,detail,instance,code` | | |
| E2 | Health probe | `GET /health` | `200`; `{status, product_id, version, timestamp}` | | |
| E3 | Auth rate limiting (optional) | Rapidly call `/auth/register` > 10×/min from one IP | Eventually `429`; `code` = `rate_limited` | | may be tuned off in some envs |

---

## Fast automated pass (optional, if you have the repo)

A one-command runner covers all of the above (plus M2). From `backend/`:
```bash
# Local
python -m scripts.api_smoke --base-url http://localhost:8000 --concurrency

# Supabase-backed (server started per §0b on :8001); USE_SUPABASE=true so the
# runner promotes its moderator in the SAME (Supabase) DB the server uses:
USE_SUPABASE=true python -m scripts.api_smoke --base-url http://localhost:8001 --concurrency
```
Expect `RESULT: N/N passed` for **both**. See `backend/API_TESTING.md` for
per-endpoint curl and `docs/ARCHITECTURE_AS_BUILT.md` for how it all fits together.

---

## Sign-off (record BOTH environments)

| Group | # Cases | Local Pass/Fail | Supabase Pass/Fail | Notes |
|---|---|---|---|---|
| A — Auth | 8 | | | |
| B — Tiers | 6 | | | |
| C — Reviews & versions | 9 | | | |
| D — AI critique | 5 | | | |
| E — Cross-cutting | 3 | | | |
| S — Supabase-specific | 4 | n/a | | |

**Local verdict:** ☐ Accepted ☐ Accepted w/ notes ☐ Rejected
**Supabase verdict:** ☐ Accepted ☐ Accepted w/ notes ☐ Rejected
**Blocking issues / bugs filed:** ______________________________________________
**Signed:** ______________  **Date:** __________

> M1 is considered **shippable only when both the Local and Supabase columns pass.**
