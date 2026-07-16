"""payouts — earnings disbursement (M3 slice 11).

The wallet is debited when a payout is *scheduled* (the money is reserved, so it
can't be double-spent while a batch is in flight) and refunded if the payout
later fails or is cancelled. Financial data: RLS is enabled with **no** public
policy, like `sessions`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import PayoutMethod, PayoutStatus


class Payout(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "payouts"
    __table_args__ = (
        Index("ix_payouts_user_id", "user_id"),
        Index("ix_payouts_status", "status"),
        Index("ix_payouts_batch_id", "batch_id"),
    )

    payout_id: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PHP", server_default="PHP")

    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payout_status"),
        default=PayoutStatus.scheduled, nullable=False,
        server_default=PayoutStatus.scheduled.value,
    )
    method: Mapped[PayoutMethod] = mapped_column(
        Enum(PayoutMethod, name="payout_method"), nullable=False
    )
    # PayPal's payout_batch_id / item id once submitted.
    provider_ref: Mapped[str | None] = mapped_column(String(128))
    # Our sender_batch_id — PayPal rejects a duplicate within 30 days, which is
    # an extra guard against double-paying a cycle.
    batch_id: Mapped[str | None] = mapped_column(String(64))

    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
