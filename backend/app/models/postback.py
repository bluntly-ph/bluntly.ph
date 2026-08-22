"""affiliate_postbacks — raw marketplace conversion signals.

**Evidence, not money.** A Lazada postback is authenticated only by a shared
secret in the URL; there is no request signature in their macro set. So a row
here records what the marketplace *claimed* and flips the originating click to
`converted`. Actual `commissions` are created from a signed source — the
`/marketing/conversion/report` Open API for Lazada, or the admin CSV import for
Shopee — and linked back via `reconciled_commission_id`.

Idempotent on (platform, external_sub_order_id): Lazada retries, and their
'Run Test' button replays mock payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import AffiliateTxStatus, Platform, SettlementStatus


class AffiliatePostback(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "affiliate_postbacks"
    __table_args__ = (
        UniqueConstraint("platform", "external_sub_order_id",
                         name="uq_postback_platform_sub_order"),
    )

    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False,
                                            default="order", server_default="order")

    external_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    # The sub-order is the per-item row and the finest grain Lazada reports, so
    # it — not the parent order — is the idempotency key.
    external_sub_order_id: Mapped[str | None] = mapped_column(String(128))

    click_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    review_sub_id: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"))
    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL"))

    reported_payout: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reported_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    order_status: Mapped[str | None] = mapped_column(String(64))
    order_type: Mapped[str | None] = mapped_column(String(64))
    attribution_type: Mapped[str | None] = mapped_column(String(64))
    conversion_time: Mapped[str | None] = mapped_column(String(64))

    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict,
                                      server_default="{}")
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True)

    reconciled_commission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commissions.id", ondelete="SET NULL"))

    # --- canonical lifecycle (0031) ----------------------------------------
    # This table is the canonical affiliate transaction store. The name is
    # historical: it was built for the Lazada postback path, but its identity
    # key — UNIQUE (platform, external_sub_order_id) — is exactly what a
    # provider-scoped idempotent upsert needs, so it was extended rather than
    # duplicated by a second table.
    canonical_status: Mapped[AffiliateTxStatus] = mapped_column(
        Enum(AffiliateTxStatus, name="affiliate_tx_status"),
        nullable=False, default=AffiliateTxStatus.pending, server_default="pending")
    settlement_status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, name="settlement_status"),
        nullable=False, default=SettlementStatus.not_earned,
        server_default="not_earned")

    #: The provider's own item-level word. Shopee reports this separately from
    #: the order-level `order_status` and the two disagree in the real report.
    raw_item_status: Mapped[str | None] = mapped_column(String(64))
    #: Why the canonical status is what it is, in one line, for the moderator.
    status_reason: Mapped[str | None] = mapped_column(String(255))

    source_conversion_id: Mapped[str | None] = mapped_column(String(128))
    source_item_id: Mapped[str | None] = mapped_column(String(128))

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))

    #: Product and seller context for the moderator view. Deliberately no buyer
    #: identity: the Lazada API returns memberEmail/memberName/memberId and none
    #: of it is stored or logged.
    seller_name: Mapped[str | None] = mapped_column(String(255))
    product_name: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120))

    source_import_id: Mapped[str | None] = mapped_column(String(64), index=True)

    #: What a reversal could not claw back because the wallet was already paid
    #: out. Recorded rather than dropped — there is no product policy for
    #: post-payout recovery, and inventing one is not engineering's call.
    unrecovered_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
