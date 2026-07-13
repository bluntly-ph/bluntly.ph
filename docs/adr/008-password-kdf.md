# ADR-008: Password KDF — delegated to Supabase

- **Status:** SUPERSEDED by [ADR-011](011-argon2id-kdf.md) in M1 (app now hashes
  passwords with Argon2id). Retained for history.
- **Context (PRD §5 Security gap, Architecture §7):** The spec has a
  `password_hash` field but names no KDF or parameters.

## Decision
Because identity is owned by Supabase Auth (ADR-001), **the application never
stores or hashes passwords.** Credential hashing is delegated to Supabase (which
uses bcrypt internally). Therefore:

- `users.password_hash` is **removed** from the schema (deviation — see changelog).
- There is **no app-level KDF** to configure; the "specify a modern KDF"
  requirement is satisfied by delegation to Supabase's managed credential store.

If a self-hosted credential path is ever introduced (not planned), it must use
**Argon2id** (or bcrypt with cost ≥ 12 if Argon2id is unavailable), and this ADR
must be superseded.

## Consequences
Smaller attack surface (no password material in our DB); one fewer secret to
manage. Trade-off: full dependency on Supabase for authentication availability.
