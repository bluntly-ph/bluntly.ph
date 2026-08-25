"""request_geo_buckets — aggregate traffic geography, one row per hour x place.

Not a request log. There is no IP column and no user column, so a row here
cannot be narrowed to a person or joined back to one; that is the property that
makes this aggregate analytics rather than tracking. See migration 0032.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestGeoBucket(Base):
    __tablename__ = "request_geo_buckets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    #: Start of the UTC hour this count covers.
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    #: Serving Vercel POP. Infrastructure, not the visitor's location.
    pop: Mapped[str | None] = mapped_column(String(8))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    request_count: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                               server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ReviewViewBucket(Base):
    """review_view_buckets — how often a review was opened, per hour.

    No user column and no IP, exactly like the geography buckets: a row says
    how many times a review was opened in an hour and cannot say by whom. See
    migration 0033.
    """

    __tablename__ = "review_view_buckets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                            server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))
