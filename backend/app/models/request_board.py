"""review_requests + request_upvotes — the request board (M3 slice 9).

A user posts a "please review this product" request. The community up-votes it,
which is how demand is expressed and how the board is ranked. A reviewer claims
it by linking their OWN review once that review is **published by the
moderator** (the existing publication gate).

Posting is free. It used to escrow a token bounty which paid out on fulfilment,
but tokens were retired in favour of the PHP revenue share and the board was the
last thing still spending them (migration 0022); a reviewer who fulfils a
request now earns through the ordinary revenue share like any other review.

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
    """One up-vote per user per request; ranks the board by demand."""

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
