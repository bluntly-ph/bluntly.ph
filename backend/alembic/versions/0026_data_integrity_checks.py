"""additive CHECK constraints for invariants only the application enforced

Audit finding: the schema had exactly two CHECK constraints
(`ck_commission_target`, `ck_token_amount_nonzero`) while the application
assumed several more. Every bound below was enforced only in Pydantic, so
anything writing directly to the database bypassed it - and things do write
directly: `seed_showcase.py`, `reset_and_seed.py`, and any admin SQL.

`star_rating` is the one that matters most. It feeds `avg_rating` and the
time-decayed Wilson ranking, so a single out-of-range row would quietly skew
the ordering the whole platform is built on, with no error anywhere.

**Additive and verified before writing.** Every constraint was checked against
production first and returned zero violations:

    star_rating 1..5            0
    reputation_score 0..100     0
    trust_stage 0..5            0
    payouts.amount > 0          0
    price_history.price > 0     0
    wallet_balance >= 0         0
    version_number >= 1         0

Adding a satisfied CHECK does not rewrite rows and cannot break deployed code -
the application already refuses to produce values that would violate them, so
no code path can start failing. It is therefore safe in either order relative
to its deploy, unlike the contracting migrations 0023 and 0024.

NOT VALID is deliberately not used: the tables are small (hundreds of rows) and
a validated constraint is worth more than the momentary lock it costs here.

Revision ID: 0026_data_integrity_checks
Revises: 0025_receipt_view_audit
"""
from __future__ import annotations

from alembic import op

revision = "0026_data_integrity_checks"
down_revision = "0025_receipt_view_audit"
branch_labels = None
depends_on = None

# (table, constraint name, expression). NULL-tolerant by design: these bound
# the value when present and say nothing about whether it must be present,
# which is the column's nullability and a separate question.
CHECKS: tuple[tuple[str, str, str], ...] = (
    ("reviews", "ck_review_star_rating", "star_rating BETWEEN 1 AND 5"),
    ("users", "ck_user_reputation_range", "reputation_score BETWEEN 0 AND 100"),
    ("users", "ck_user_trust_stage_range", "trust_stage BETWEEN 0 AND 5"),
    ("users", "ck_user_wallet_non_negative", "wallet_balance >= 0"),
    ("payouts", "ck_payout_amount_positive", "amount > 0"),
    ("price_history", "ck_price_positive", "price > 0"),
    ("review_versions", "ck_version_number_positive", "version_number >= 1"),
)


def upgrade() -> None:
    for table, name, expression in CHECKS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression})")


def downgrade() -> None:
    for table, name, _ in CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
