"""sessions — affiliate click tracking with a PII retention lifecycle.

PII schedule (Architecture §4, enforced by a Celery job in M2):
  * user_agent purged at 90 days
  * ip_address hashed into ip_hash at 30 days, deleted at 90 days
`ua_purge_at`, `ip_hash_at`, `ip_delete_at` are precomputed on insert so the
retention job is a simple time-window sweep.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import ConversionStatus, Platform


class Session(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "sessions"

    session_id: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)

    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    destination_url: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform, name="platform"))

    # References used to reconcile against imported commission CSV rows (§3.3).
    click_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    order_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    conversion_status: Mapped[ConversionStatus] = mapped_column(
        Enum(ConversionStatus, name="conversion_status"),
        default=ConversionStatus.clicked, nullable=False,
        server_default=ConversionStatus.clicked.value,
    )
    order_status: Mapped[str | None] = mapped_column(String(64))

    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # PII fields + precomputed retention deadlines.
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    ua_purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ip_hash_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ip_delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
