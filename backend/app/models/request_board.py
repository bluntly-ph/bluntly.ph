"""review_requests + request_upvotes — the request board (M3 slice 9).

A user posts a "please review this product" request and escrows a token bounty
from their balance. The community up-votes it, which raises a platform-minted
top-up. A reviewer claims it by linking their OWN review once that review is
**published by the moderator** (the existing publication gate); bounty + top-up
then pay out to the reviewer.

`source_url` is a marketplace link the requester pastes. It is stored and shown
to humans and **never fetched** — the no-scraping mandate applies here too.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import RequestStatus


class ReviewRequest(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "review_requests"
    __table_args__ = (
        Index("ix_review_requests_status", "status"),
        Index("ix_review_requests_expires_at", "expires_at"),
    )

    request_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)

    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)  # never fetched

    bounty: Mapped[int] = mapped_column(Integer, nullable=False)  # tokens escrowed
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        default=RequestStatus.open, nullable=False,
        server_default=RequestStatus.open.value,
    )
    fulfilled_by_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upvote_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # AI screening verdict at creation: {"valid": bool, "reasons": [...], "provider": ...}
    ai_validation: Mapped[dict | None] = mapped_column(JSONB)


class RequestUpvote(Base, UUIDPrimaryKey):
    """One up-vote per user per request; raises the platform top-up."""

    __tablename__ = "request_upvotes"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_request_upvote_once"),
        Index("ix_request_upvotes_request_id", "request_id"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
