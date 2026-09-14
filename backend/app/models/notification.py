"""In-app notifications (FR-1 1.6).

One row per thing that happened to one account's own content: a review
published, rejected or taken down; a question answered; an answer picked as
best; a store claim, a seller review or a price report decided. Rows are
written in the same transaction as the event that causes them, so a
notification never announces a decision that was rolled back.

`read_at` is the read state (NULL = unread). `link` is a same-site path only —
the service drops anything else before it is stored.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # The list: one account, newest first.
        Index("ix_notifications_user_created", "user_id", "created_at"),
        # The unread badge counts this on every page load for a signed-in reader.
        Index("ix_notifications_unread", "user_id",
              postgresql_where=text("read_at IS NULL")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: A stable machine name ("review_rejected"), for grouping and tests.
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    #: An excerpt, never the full content.
    body: Mapped[str | None] = mapped_column(Text)
    #: A same-site path, or NULL.
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
