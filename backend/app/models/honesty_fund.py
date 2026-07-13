"""honesty_fund_distributions (FR-6).

Monthly Celery cycle: pool = 30% of cycle commissions; each eligible <=2-star
earn_eligible review's payout = (its Honesty Score / total eligible Honesty
Scores) x pool. One row per (cycle_month, review).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class HonestyFundDistribution(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "honesty_fund_distributions"
    __table_args__ = (
        UniqueConstraint("cycle_month", "review_id", name="uq_hfd_cycle_review"),
    )

    distribution_id: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)
    cycle_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    honesty_score: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    pool_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payout_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
