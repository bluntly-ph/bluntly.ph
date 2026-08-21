# CI workflow — activated 2026-08-21

The workflow now lives at **`.github/workflows/ci.yml`**, where GitHub actually
runs it. This directory keeps only these notes.

It sat here from 2026-08-19 providing no protection at all, because the
credential in use lacked GitHub's `workflow` OAuth scope and GitHub refuses any
push that creates or edits a file under `.github/workflows/` without it:

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or
  update workflow `.github/workflows/ci.yml` without `workflow` scope)
```

Worth knowing if it ever has to move again: the rejected push still leaves the
commit sitting on the local branch, and every subsequent push then fails on the
same rule. Back it out (`git reset --soft HEAD~1`, restore the file) before
continuing, or unrelated work piles up behind a commit that can never land.

The scope was granted with:

```bash
gh auth refresh -h github.com -s workflow
```

## What it runs

Everything below needs **no secrets**.

| Job | Purpose |
|---|---|
| `guard` | The important one. Runs the guard's unit tests, then asserts that a *simulated production target is actually refused* — so the protection cannot rot silently. |
| `backend` | pytest (DB-backed tests skip themselves), plus the migration safety report. |
| `frontend` | `tsc --noEmit`, `npm run lint`, `npm run build`. |
| `backend-db-tests` | Opt-in. Runs the full suite against the isolated test project, and only when its secrets are present. |

## Secrets for the DB-backed job

Add under **Settings → Secrets and variables → Actions**. Without them that job
skips with a notice; it can never fall back to production, because the guard
refuses a production target regardless of configuration.

| Secret | Value |
|---|---|
| `TEST_SUPABASE_SESSION_POOLER` | Session-pooler connection string for `bluntly-ph-test` |
| `TEST_SUPABASE_URL` | `https://miysywhcdqkoniaibglx.supabase.co` |
| `TEST_SUPABASE_SECRET_KEY` | That project's service-role key |

Never add production credentials here. See `docs/ENVIRONMENTS.md`.
