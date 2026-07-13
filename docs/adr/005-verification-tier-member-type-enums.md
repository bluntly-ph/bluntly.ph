# ADR-005: `verification_tier` and `member_type` enums

- **Status:** Accepted (M0)
- **Context (PRD A4, Architecture §4):** The schema implies tiering models
  (`verification_tier` default `tier_0`; `member_type`) the narrative never defines.

## Decision
Enumerate concrete values now (in `app/models/enums.py`), even where only one is
active at launch:

- **`verification_tier`**: `tier_0` (default, active) | `tier_1` (reserved for a
  future stronger-proof tier, e.g. receipt-verified). Only `tier_0` is set by any
  M0/M1/M2 logic.
- **`member_type`**: `shopper` | `seller` | `moderator`. Mirrors `role`; retained
  because the Data Dictionary carries the field. Kept in sync with `role` at the
  service layer.

## Consequences
Schema is concrete and migratable. `tier_1` semantics are deferred; no logic
branches on it until a future ADR defines its unlock criteria.
