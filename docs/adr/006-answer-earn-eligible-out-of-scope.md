# ADR-006: Answer-level `earn_eligible` is out of scope

- **Status:** Accepted (M0)
- **Context (PRD A5):** The `answers` table carries an `earn_eligible` flag, but
  the spec never describes answer-level earning.

## Decision
Answer-level earning is **out of scope** for this build (M0–M2). The
`answers.earn_eligible` column is **retained** (Data-Dictionary fidelity) but is
**not wired** to any voting, gate, moderation, or payout logic. It defaults to
`false` and nothing mutates it.

The `commissions` table still supports an `answer` target (`target_type='answer'`)
at the schema level for forward-compatibility, but no code path creates such rows.

## Consequences
If answer earning is later scoped, the column and commission target already exist;
only the service logic and a future ADR are needed. No dead logic ships now.
