# ADR-012: Membership tiers (Special / Founding / Standard)

- **Status:** Accepted (M1)
- **Context:** M1 requires "membership tier management (Special, Founding,
  Standard)" — a concept distinct from the reputation/trust stages in the original
  capstone docs.

## Decision
Two related constructs:
- **`users.membership_tier`** — an enum (`special` | `founding` | `standard`,
  default `standard`) identifying each user's tier. Distinct from `trust_stage`
  (reputation) and from `role` (RBAC).
- **`membership_tiers`** table — one config row per tier code, holding the
  manageable parameters: `name`, `description`, `revenue_share_bps` (reviewer's
  revenue share in basis points; feeds the M2 tier-based split), `payout_priority`
  (payout scheduling order, M3), `benefits` (JSONB), `is_active`.

Endpoints: `GET /membership-tiers` (public), `GET /membership-tiers/{code}`,
`PATCH /membership-tiers/{code}` (moderator config), `PATCH /users/{id}/membership-tier`
(moderator assignment). New users default to `standard`.

## Consequences
Tier parameters are DB-managed (admin-editable) rather than hardcoded, so the M2
revenue split and M3 payout scheduling read tier config rather than constants.
