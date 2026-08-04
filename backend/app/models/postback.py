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
from app.models.enums import Platform


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
