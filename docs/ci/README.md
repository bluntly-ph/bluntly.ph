# CI workflow — needs one manual step

`ci.yml` in this directory is a complete, working GitHub Actions workflow. It
is **not** at `.github/workflows/ci.yml` because the credential available to
the agent that wrote it lacks GitHub's `workflow` OAuth scope, and GitHub
refuses any push that creates or edits a file under `.github/workflows/`
without it:

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or
  update workflow `.github/workflows/ci.yml` without `workflow` scope)
```

To activate it, from a credential that has the scope (a normal `git push` from
the owner's machine is enough):

```bash
mkdir -p .github/workflows
git mv docs/ci/ci.yml .github/workflows/ci.yml
git commit -m "ci: activate the GitHub Actions workflow"
git push
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
