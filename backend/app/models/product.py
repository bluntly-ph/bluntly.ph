"""products, product_platforms, price_history.

Manual-first canonicalization (§3.1): a product is submitted via `source_url`
with status `pending`; an admin sets the canonical name fields and flips it to
`canonicalized`. No automated fetch of the URL ever happens.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import ImageSource, Platform, ProductStatus


class Product(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "products"

    product_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)

    # Canonical name components (Brand, Line/Series, Key Spec/Variant, Descriptor).
    canonical_name: Mapped[str | None] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(120))
    line: Mapped[str | None] = mapped_column(String(120))
    key_spec: Mapped[str | None] = mapped_column(String(120))
    descriptor: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120), index=True)

    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status"),
        default=ProductStatus.pending, nullable=False,
        server_default=ProductStatus.pending.value,
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    # Product listing imagery. Distinct from a review's proof photo: this is the
    # merchant's picture of the item, not evidence that a reviewer owns one.
    image_url: Mapped[str | None] = mapped_column(Text)
    image_source: Mapped[ImageSource] = mapped_column(
        Enum(ImageSource, name="image_source"),
        default=ImageSource.none, nullable=False,
        server_default=ImageSource.none.value,
    )
    image_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Denormalized aggregates (updated in service-layer transactions — ADR/changelog).
    avg_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=0, nullable=False, server_default="0"
    )
    review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Time-decayed Wilson trust over published reviews' star_rating >= 4 (M2 slice 4).
    trust_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=0, nullable=False, server_default="0"
    )
    aggregated_pros: Mapped[dict | None] = mapped_column(JSONB)
    aggregated_cons: Mapped[dict | None] = mapped_column(JSONB)

    platforms: Mapped[list[ProductPlatform]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductPlatform(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "product_platforms"
    __table_args__ = (
        UniqueConstraint("product_id", "platform", "platform_url", name="uq_product_platform"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), nullable=False)
    platform_url: Mapped[str | None] = mapped_column(Text)
    # A6: Lazada may have no affiliate relationship -> not monetizable until resolved.
    is_monetizable: Mapped[bool] = mapped_column(default=True, server_default="true")

    product: Mapped[Product] = relationship(back_populates="platforms")


class PriceHistory(Base, UUIDPrimaryKey, Timestamps):
    """Community-submitted price observations (§3.4). Never scraped."""

    __tablename__ = "price_history"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(120))
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
