"""review_contracts — revenue-share contracts on monetized reviews (M3 slice 10).

Every monetized review runs a contract. While it is `active`, commissions split
by the reviewer's membership tier (M2 slice 6). At term end it auto-renews unless
the reviewer turned that off; once `expired` or `bought_out` the reviewer's share
drops to zero and that share goes to the platform (the Honesty Fund's fixed 30%
never changes).

A buyout is a one-time PHP wallet credit offered by a moderator: the reviewer
accepts (paid once, contract ends) or rejects (contract untouched).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import ContractStatus


class ReviewContract(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "review_contracts"
    # Exactly one ACTIVE contract per review — enforced by a partial unique index
    # created in the migration (uq_contract_active).

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, name="contract_status"),
        default=ContractStatus.active, nullable=False,
        server_default=ContractStatus.active.value,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    renewal_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # --- Buyout (one pending offer at a time) ---
    buyout_offer_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    buyout_offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyout_offered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    buyout_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyout_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
