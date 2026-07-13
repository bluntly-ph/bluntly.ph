# ADR-002: Compute host vs. Supabase responsibility split

- **Status:** Accepted (M0), provider low-lock-in
- **Context (Architecture §5/§8 Q2, PRD A7):** The spec says "AWS, GCP, or Azure"
  but selects none, and never states who runs FastAPI/Redis/Celery relative to
  Supabase.

## Decision
Two planes:
1. **Container plane** — FastAPI API, Redis, and Celery worker/beat run as
   containers (see `backend/docker-compose.yml` locally). For staging/production
   the target is a **single container host** in or near **Singapore (ap-southeast)**
   for Philippine latency (e.g. Azure Container Apps / Fly.io / Render class). The
   code is host-agnostic (12-factor, env-driven), so the specific provider is a
   low-lock-in deployment choice, not an architectural one.
2. **Managed data plane** — **Supabase** (its own cloud, ap-southeast) remains a
   separate managed service providing Postgres, Auth, Storage, and backups/PITR.

## Consequences — RA 10173 (Data Privacy Act)
Personal data (profiles, `payout_account`, session IP/UA, wallet balances) resides
in Supabase and transits the container host. Both are **outside the Philippines**
(regional cloud), so this is a **cross-border transfer** requiring a documented
transfer basis, a privacy notice, and an NPC-registration assessment before public
launch (tracked in the M0 privacy checklist, completed in M3).
