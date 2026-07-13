# ADR-010: FastAPI-native JWT/OAuth2 auth (supersedes ADR-001)

- **Status:** Accepted (M1). **Supersedes ADR-001** (Supabase Auth as identity).
- **Context:** The M1 milestone (`docs/MILESTONES.md`) specifies "FastAPI JWT/OAuth2
  authentication, user registration and login." The product owner confirmed
  (2026-07-12) a self-hosted auth model over the M0 Supabase-Auth approach.

## Decision
Identity is owned by this service:
- **Registration** (`POST /api/v1/auth/register`) and **login**
  (`POST /api/v1/auth/login`, OAuth2 password flow) create/verify accounts.
- Passwords are hashed with **Argon2id** (ADR-011) and stored in `users.password_hash`.
- The API mints and validates its own **HS256 JWT** access tokens (`JWT_SECRET`,
  `iss=bluntly-ph`, `sub=users.id`, `role`, `exp`).
- `get_current_user` resolves the ORM `User` from the token `sub`; RBAC roles come
  from `users.role` (DB), never trusted directly from the token.
- Supabase is retained **only** for Postgres and (later) Storage — no longer identity.

## Consequences
- `users.password_hash` is **restored** (dropped in M0 under ADR-008); ADR-008 is
  superseded by ADR-011. `users.id` becomes an ordinary generated PK (default
  `gen_random_uuid()`), no longer the Supabase uid.
- The Supabase-JWKS validation and `SUPABASE_JWKS_URL` from M0 are no longer used
  for request auth. RLS policies (keyed on `auth.uid()`) are now effectively
  dormant defense-in-depth, since the backend connects as the DB owner and enforces
  RBAC itself — kept for any future Supabase-direct access.
