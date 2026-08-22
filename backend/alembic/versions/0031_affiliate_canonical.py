"""canonical affiliate transaction lifecycle + auditable commission reversal

`affiliate_postbacks` already carried the right idempotency shape —
`UNIQUE (platform, external_sub_order_id)` — and the attribution and money
columns. It was named for the Lazada postback path, but structurally it is
"one provider-reported affiliate transaction". So it is extended here rather
than duplicated by a parallel table.

The identity key is reused as-is, because it is already correct for both
providers once each adapter synthesises the right value. Verified against the
owner's real reports rather than assumed:

* Lazada — `Sub Order ID` is unique on its own: 218 distinct in 218 rows.
* Shopee — nothing obvious is. `Order id` collides 29 times, and even
  `Order + Conversion + Item + Model` still collides 3 times. All three
  collisions are one group of four rows that differ only by `Promotion id`
  (`..._1`, `..._2`, `..._3`, blank) — promotion splits of one physical item,
  only one of which carries commission. Adding `Promotion id` gives
  108 distinct in 108 rows.

Expand-only. Every column is nullable or carries a server default, no existing
column changes type, and nothing is dropped, so old code keeps running against
the new schema. `affiliate_postbacks` and `commissions` are both empty in
production, so there is nothing to backfill.

Revision ID: 0031_affiliate_canonical
Revises: 0030_tier_share_bounds
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0031_affiliate_canonical"
down_revision = "0030_tier_share_bounds"
branch_labels = None
depends_on = None

TX_STATUS = ("pending", "completed", "cancelled", "returned")
SETTLEMENT = ("not_earned", "earned", "paid", "reversed")


def upgrade() -> None:
    tx = sa.Enum(*TX_STATUS, name="affiliate_tx_status")
    st = sa.Enum(*SETTLEMENT, name="settlement_status")
    tx.create(op.get_bind(), checkfirst=True)
    st.create(op.get_bind(), checkfirst=True)

    # --- the canonical lifecycle -------------------------------------------
    # Defaults to `pending`, which is the safe direction: a row nobody has
    # classified yet must never look like money.
    op.add_column("affiliate_postbacks", sa.Column(
        "canonical_status", tx, nullable=False, server_default="pending"))
    op.add_column("affiliate_postbacks", sa.Column(
        "settlement_status", st, nullable=False, server_default="not_earned"))

    # The provider's own words, kept verbatim for audit. `order_status` already
    # exists and holds the order-level string; Shopee also reports an item-level
    # one, and the two disagree in the real report.
    op.add_column("affiliate_postbacks", sa.Column(
        "raw_item_status", sa.String(64), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "status_reason", sa.String(255), nullable=True))

    # Provider identifiers beyond the sub-order used as the key.
    op.add_column("affiliate_postbacks", sa.Column(
        "source_conversion_id", sa.String(128), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "source_item_id", sa.String(128), nullable=True))

    # Lifecycle timestamps. Nullable because no provider reports all three.
    op.add_column("affiliate_postbacks", sa.Column(
        "completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "returned_at", sa.DateTime(timezone=True), nullable=True))

    # Money the provider reports about the sale itself.
    op.add_column("affiliate_postbacks", sa.Column(
        "refund_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "commission_rate", sa.Numeric(7, 4), nullable=True))

    # Product/seller context, for the moderator view. Never buyer identity:
    # Lazada's API returns memberEmail/memberName/memberId and none of it is
    # stored here.
    op.add_column("affiliate_postbacks", sa.Column(
        "seller_name", sa.String(255), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "product_name", sa.String(255), nullable=True))
    op.add_column("affiliate_postbacks", sa.Column(
        "category", sa.String(120), nullable=True))

    # Which import produced or last touched this row.
    op.add_column("affiliate_postbacks", sa.Column(
        "source_import_id", sa.String(64), nullable=True))

    # What a reversal could not take back because the wallet had already been
    # paid out. Recorded rather than silently dropped; there is no product
    # policy for post-payout recovery, and inventing one is not engineering's
    # call.
    op.add_column("affiliate_postbacks", sa.Column(
        "unrecovered_amount", sa.Numeric(12, 2), nullable=True))

    op.create_index("ix_postback_canonical_status", "affiliate_postbacks",
                    ["canonical_status"])
    op.create_index("ix_postback_import", "affiliate_postbacks", ["source_import_id"])

    # --- auditable reversal -------------------------------------------------
    # A return does not rewrite the original commission. It writes a second,
    # opposing row that points at the first, so the pair sums to the truth and
    # the history of both events survives.
    op.add_column("commissions", sa.Column(
        "reverses_commission_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_commission_reverses", "commissions", "commissions",
                          ["reverses_commission_id"], ["id"], ondelete="SET NULL")
    # One reversal per original. Partial, so the many NULLs do not collide.
    op.create_index("uq_commission_one_reversal", "commissions",
                    ["reverses_commission_id"], unique=True,
                    postgresql_where=sa.text("reverses_commission_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_commission_one_reversal", table_name="commissions")
    op.drop_constraint("fk_commission_reverses", "commissions", type_="foreignkey")
    op.drop_column("commissions", "reverses_commission_id")

    op.drop_index("ix_postback_import", table_name="affiliate_postbacks")
    op.drop_index("ix_postback_canonical_status", table_name="affiliate_postbacks")
    for column in ("unrecovered_amount", "source_import_id", "category",
                   "product_name", "seller_name", "commission_rate",
                   "refund_amount", "returned_at", "completed_at",
                   "source_item_id", "source_conversion_id", "status_reason",
                   "raw_item_status", "settlement_status", "canonical_status"):
        op.drop_column("affiliate_postbacks", column)

    sa.Enum(name="settlement_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="affiliate_tx_status").drop(op.get_bind(), checkfirst=True)
