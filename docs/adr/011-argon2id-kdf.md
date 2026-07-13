# ADR-011: Argon2id password hashing (supersedes ADR-008)

- **Status:** Accepted (M1). **Supersedes ADR-008** (KDF delegated to Supabase).
- **Context:** With FastAPI-native auth (ADR-010), the app stores and verifies
  passwords itself, so it needs a modern KDF (PRD §5 security gap).

## Decision
Use **Argon2id** via `argon2-cffi`'s `PasswordHasher` with library defaults
(t=3, m=64 MiB, p=4 at time of writing). `hash_password` / `verify_password` live in
`app/core/security.py`. `check_needs_rehash` is available to transparently upgrade
parameters over time. Hashes are stored in `users.password_hash` (nullable, so
admin/seed accounts may exist without a local password).

## Consequences
Argon2id is the current OWASP-recommended password KDF (memory-hard, resistant to
GPU/ASIC attacks). Verification is intentionally slow (~tens of ms) — acceptable on
auth endpoints, which are also rate-limited (ADR-009).
