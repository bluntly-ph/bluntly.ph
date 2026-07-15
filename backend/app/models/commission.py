"""commissions (FR-6, §3.3).

Reconciled from admin-imported Shopee/Lazada CSVs. The 40/30/30 split is stored
as explicit share columns. Idempotency: (csv_source, row_reference) is unique so
re-uploading the same CSV cannot double-count.

Deviation (changelog): the spec's polymorphic `commissions.review_id` TEXT (which
could point at a review OR an answer with no FK integrity) is replaced by a
`target_type` enum + nullable typed FKs `review_id` / `answer_id`.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import CommissionTarget, MembershipTier


class Commission(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "commissions"
    __table_args__ = (
        UniqueConstraint("csv_source", "row_reference", name="uq_commission_csv_row"),
        CheckConstraint(
            "(target_type = 'review' AND review_id IS NOT NULL AND answer_id IS NULL) OR "
            "(target_type = 'answer' AND answer_id IS NOT NULL AND review_id IS NULL)",
            name="ck_commission_target",
        ),
    )

    commission_id: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)

    target_type: Mapped[CommissionTarget] = mapped_column(
        Enum(CommissionTarget, name="commission_target"), nullable=False
    )
    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL")
    )
    answer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("answers.id", ondelete="SET NULL")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Tier snapshot at reconciliation time (M2 slice 6) — immutable audit.
    reviewer_tier: Mapped[MembershipTier | None] = mapped_column(
        Enum(MembershipTier, name="membership_tier"))
    reviewer_share_bps: Mapped[int | None] = mapped_column(Integer)

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    platform_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reviewer_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    honesty_fund_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PHP", server_default="PHP")

    csv_source: Mapped[str] = mapped_column(String(255), nullable=False)
    row_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    order_status: Mapped[str | None] = mapped_column(String(64))
    is_disputed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    cycle_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # YYYY-MM-01
