# Documentation Index: Bluntly.ph Frontend

**Project slug:** `bluntly-fe`
**Maintained by:** Bluntly.ph frontend track
**Last updated:** 2026-07-20
**Built on FMD v1.28.1**

> This manifest governs the **frontend** documentation suite only. The frontend is a
> separate delivery track from the backend (which is built through M3 and documented in
> the parent [`docs/`](../) folder). Frontend docs live here in `docs/frontend/`; they
> consume the backend strictly as a read-only API contract via
> [`../openapi.json`](../openapi.json) and [`../FRONTEND_INTEGRATION.md`](../FRONTEND_INTEGRATION.md).
> Do not edit backend code or backend docs from the frontend track.

---

## 1. Document Suite

Core technical suite (dev / design / prod docs). Business docs (BRD, UES, GTM, PITCH,
WRAP) are intentionally out of scope for this track.

| Document | File | Version | Status | Last Updated | Last Reconciled |
|----------|------|---------|--------|--------------|-----------------|
| PRD · Product Requirements | [prd-bluntly-fe.md](prd-bluntly-fe.md) | 0.1 | Draft | 2026-07-20 | N/A |
| DSD · Design System | [dsd-bluntly-fe.md](dsd-bluntly-fe.md) | 0.1 | Draft | 2026-07-20 | N/A |
| SDD · System Design | [sdd-bluntly-fe.md](sdd-bluntly-fe.md) | 0.1 | Draft | 2026-07-20 | N/A |
| QAD · QA & Test Plan | [qad-bluntly-fe.md](qad-bluntly-fe.md) | 0.1 | Draft | 2026-07-20 | N/A |
| BUILD · Build Guide | [build-bluntly-fe.md](build-bluntly-fe.md) | 0.1 | Draft | 2026-07-20 | N/A |

**Materialized at project root (not in `docs/frontend/`):** `README.md`, `BRAND.md`,
`DESIGN.md`, `AGENTS.md` (frontend scope). Their status and reconciliation live with the
canonical source doc: BRAND/DESIGN with the DSD, AGENTS with the BUILD guide.

**Not written (out of scope for the frontend track):** IDEA, VALIDATION, SCRUTINY, BRD,
UES, SAD, RFC, CLR, AIA, GTM, OPS, PITCH, WRAP. The AI critique surface is a UI onto the
backend's existing critique service, so no frontend AIA is required; the backend owns the
model assurance.

### 1.1 Traceability Matrix

Must-Have `PRD-F#` coverage across the suite. Keep current when PRD/SDD/QAD are locked or
amended.

| PRD-F# | Feature (short) | Milestone | Priority | In SDD | In QAD |
|--------|-----------------|-----------|----------|--------|--------|
| PRD-F1 | Responsive layout shell + global nav | FE-M1 | Must-Have | yes | yes |
| PRD-F2 | Landing page (logged-out / logged-in) | FE-M1 | Must-Have | yes | yes |
| PRD-F3 | Registration (sign up) | FE-M1 | Must-Have | yes | yes |
| PRD-F4 | Login | FE-M1 | Must-Have | yes | yes |
| PRD-F5 | Forgot-password flow | FE-M1 | Must-Have | yes | yes |
| PRD-F6 | User dashboard & profile | FE-M1 | Must-Have | yes | yes |
| PRD-F7 | Product/seller listings with search & filter | FE-M2 | Must-Have | yes | yes |
| PRD-F8 | Review detail (stars + reputation) | FE-M2 | Must-Have | yes | yes |
| PRD-F9 | Review creation flow with AI critique | FE-M2 | Must-Have | yes | yes |
| PRD-F10 | Seller review flow | FE-M2 | Must-Have | yes | yes |
| PRD-F11 | Upvote/downvote & report UI | FE-M2 | Must-Have | yes | yes |
| PRD-F12 | Affiliate link display | FE-M2 | Must-Have | yes | yes |
| PRD-F13 | Q&A flow | FE-M2 | Should-Have | yes | yes |
| PRD-F14 | Membership tier & pricing pages | FE-M3 | Must-Have | yes | yes |
| PRD-F15 | Token balance & transaction history | FE-M3 | Must-Have | yes | yes |
| PRD-F16 | Request board interface | FE-M3 | Must-Have | yes | yes |
| PRD-F17 | Earnings & payout-history dashboard | FE-M3 | Must-Have | yes | yes |
| PRD-F18 | Monetized-review contracts UI | FE-M3 | Should-Have | yes | yes |
| PRD-F19 | Cross-browser & responsive quality | FE-M3 | Must-Have | N/A | yes |
| PRD-F20 | Production deploy & end-to-end integration | FE-M3 | Must-Have | yes | yes |

A Must-Have with `no` in SDD or QAD is a gap; close it or cut the feature via a Change
Record. `PRD-F19` is a non-functional quality gate owned by the QAD, so `N/A` in SDD is
expected.

---

## 2. Change Log

Every material change to a Locked document is recorded as a Change Record. Newest first.

| CR ID | Date | Summary | Trigger doc | Docs touched | File |
|-------|------|---------|-------------|--------------|------|
| (none yet) | | | | | |

---

## 3. Incident Log (Postmortems)

| PM ID | Incident date | Severity | Summary | Action items closed? | File |
|-------|---------------|----------|---------|----------------------|------|
| (none yet) | | | | | |

---

## 4. Health Check

Quick triage an agent runs at the start of a session. Anything that fails gets surfaced.

- [ ] Every Locked doc's **Last Reconciled** date is newer than the last frontend code change to its area.
- [ ] No doc has been in `Draft` longer than expected without movement.
- [ ] Feature IDs (`PRD-F#`) referenced by SDD / QAD / BUILD still exist in the PRD.
- [ ] §1.1 Traceability Matrix matches Must-Have coverage.
- [ ] The BUILD guide's pinned versions and golden-path samples have been re-verified recently.
- [ ] Frontend consumes only the documented backend contract; no direct backend edits from this track.
- [ ] **Production Readiness Gate:** QAD Must-Have coverage green, DSD §8 accessibility gate clear, PRD §9 rollback defined, BUILD stack pinned, cross-browser + responsive matrices executed (PRD-F19).
- [ ] **Validator:** `python fmd/scripts/check.py docs/frontend/` passes voice, coverage, matrix, and currency. One expected FAIL remains (`docs: no index.md`) because this FMD suite lives under `docs/frontend/`, not at the `docs/` root, to keep the frontend track separate from the non-FMD backend docs. See §5.

---

## 5. Notes

The backend milestones (M1 done, M2 done, M3 built) are tracked separately in
[`../MILESTONES.md`](../MILESTONES.md). The three frontend milestones (FE-M1, FE-M2,
FE-M3) are defined in [`prd-bluntly-fe.md`](prd-bluntly-fe.md) §3 and tested per milestone
in [`qad-bluntly-fe.md`](qad-bluntly-fe.md).

**Validator scoping (intentional deviation).** `fmd/scripts/check.py` assumes one FMD suite
rooted at a folder named `docs/` with its manifest at `docs/index.md`. This repo's `docs/` is a
mixed tree: the FMD-managed frontend suite in `docs/frontend/` plus the pre-existing, non-FMD
backend docs directly in `docs/`. We keep this manifest at `docs/frontend/index.md` (not
`docs/index.md`) so the frontend track stays cleanly separated and so the validator never scans
or reports on the backend docs. The single `docs: no index.md` FAIL is the accepted cost of that
separation; all substantive checks (voice, PRD-F# coverage, template roster, currency) pass.
