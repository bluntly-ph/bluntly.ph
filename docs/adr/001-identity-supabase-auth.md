# ADR-001: Supabase Auth is the single source of identity

- **Status:** SUPERSEDED by [ADR-010](010-fastapi-native-auth.md) in M1 (identity
  moved to FastAPI-native JWT/OAuth2). Retained for history.
- **Context (PRD §8 A?, Architecture §2 / §8 Q1):** The source spec assigns
  authentication to *both* Supabase and a FastAPI/Redis session system. Running
  two identity systems invites RLS/RBAC drift.

## Decision
Supabase Auth is the **single source of identity**. Every protected FastAPI
request carries a Supabase-issued JWT, validated server-side against the project
**JWKS** (`SUPABASE_JWKS_URL`, asymmetric RS256/ES256). Redis holds **only**
application data (rate-limit counters, ephemeral cache) — never identity or
sessions.

The app `users` table is a **profile** table whose primary key equals the JWT
`sub` (the Supabase `auth.users.id`). We do **not** create a hard cross-schema FK
to `auth.users`, so the identical Alembic migration runs on both local Postgres
(no Supabase auth schema) and Supabase. RBAC roles are resolved from `users.role`,
never trusted directly from token claims.

## Consequences
- No app-level password storage (see ADR-008); `users.password_hash` is dropped.
- RLS policies key on `auth.uid()` (Supabase built-in; a shim is created locally).
- One identity model → no dual-auth drift.
