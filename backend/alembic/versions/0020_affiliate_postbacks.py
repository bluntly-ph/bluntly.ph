"""affiliate_postbacks — raw conversion signals from marketplace postbacks

Lazada fires a postback per order on a D+1 basis. The postback carries no
signature — it is authenticated only by a shared secret in the URL — so rows here
are **evidence, not money**: they record what the marketplace claimed, flip the
originating click to `converted`, and are reconciled later against the signed
`/marketing/conversion/report` API (or, for Shopee, the manual CSV) which is what
actually creates `commissions`.

Idempotent on (platform, external_sub_order_id): Lazada retries, and the 'Run
Test' button replays mock payloads.

Revision ID: 0020_affiliate_postbacks
Revises: 0019_product_image
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_affiliate_postbacks"
down_revision = "0019_product_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affiliate_postbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        # The `platform` enum already exists (0002); reference it without trying
        # to re-CREATE TYPE, which sa.Enum would do.
        sa.Column("platform", postgresql.ENUM(name="platform", create_type=False),
                  nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="order"),
        # Marketplace identifiers. sub-order is the per-item row and the finest
        # grain Lazada reports, so it is the idempotency key.
        sa.Column("external_order_id", sa.String(128)),
        sa.Column("external_sub_order_id", sa.String(128)),
        # Our attribution keys, echoed back through subId1/subId2.
        sa.Column("click_ref", sa.String(128)),
        sa.Column("review_sub_id", sa.String(64)),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id", ondelete="SET NULL")),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="SET NULL")),
        # Reported figures — untrusted until the signed report confirms them.
        sa.Column("reported_payout", sa.Numeric(12, 2)),
        sa.Column("reported_amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("order_status", sa.String(64)),
        sa.Column("order_type", sa.String(64)),
        sa.Column("attribution_type", sa.String(64)),
        sa.Column("conversion_time", sa.String(64)),
        # Full query string, for disputes and for fields we do not model yet.
        sa.Column("raw", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        # Set once a signed source confirms this row and a commission exists.
        sa.Column("reconciled_commission_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("commissions.id", ondelete="SET NULL")),
        sa.UniqueConstraint("platform", "external_sub_order_id",
                            name="uq_postback_platform_sub_order"),
    )
    op.create_index("ix_affiliate_postbacks_click_ref", "affiliate_postbacks", ["click_ref"])
    op.create_index("ix_affiliate_postbacks_order", "affiliate_postbacks",
                    ["external_order_id"])
    op.create_index("ix_affiliate_postbacks_received_at", "affiliate_postbacks",
                    ["received_at"])

    # Dormant defence in depth, matching every other table (0002_rls_policies):
    # nothing reaches this table except the service role.
    op.execute("ALTER TABLE public.affiliate_postbacks ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_affiliate_postbacks_received_at", table_name="affiliate_postbacks")
    op.drop_index("ix_affiliate_postbacks_order", table_name="affiliate_postbacks")
    op.drop_index("ix_affiliate_postbacks_click_ref", table_name="affiliate_postbacks")
    op.drop_table("affiliate_postbacks")
