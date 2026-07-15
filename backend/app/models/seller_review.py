"""seller_reviews (FR-4).

Four dimensions: accuracy (binary), order completeness (binary), customer service
(1-5), packaging quality (1-5), plus overall rating (1-5) and would_recommend.
Sellers are users with role=seller; a seller_review targets that seller user.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class SellerReview(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "seller_reviews"
    __table_args__ = (
        # One seller review per (seller, reviewer) — M2 slice 4.
        UniqueConstraint("seller_id", "reviewer_id", name="uq_seller_review_once"),
    )

    seller_review_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )

    # accuracy: accurate vs. "not the same"; order_completeness: exact vs. missing item.
    accuracy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    order_completeness: Mapped[bool] = mapped_column(Boolean, nullable=False)
    customer_service: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1..5
    packaging_quality: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1..5
    overall_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1..5
    would_recommend: Mapped[bool] = mapped_column(Boolean, nullable=False)

    proof_url: Mapped[str | None] = mapped_column(Text)  # for store-name cross-check
