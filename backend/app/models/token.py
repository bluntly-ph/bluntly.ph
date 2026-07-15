"""token_transactions — append-only token ledger (M2 slice 7).

Every balance change is a ledger row with the resulting `balance_after`, so the
chain is auditable end to end. There are NO update/delete endpoints, ever.
Earning kinds are idempotent per (user, kind, ref_id) via a partial unique index
— a given review/commission can award tokens exactly once. Spending rules and
request-board rewards are M3.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey
from app.models.enums import TokenKind


class TokenTransaction(Base, UUIDPrimaryKey):
    __tablename__ = "token_transactions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_token_amount_nonzero"),
        Index("ix_token_tx_user_created", "user_id", "created_at"),
        # Partial unique idempotency index uq_token_once lives in the migration
        # (WHERE ref_id IS NOT NULL AND kind LIKE 'earn_%').
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # signed, != 0
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TokenKind] = mapped_column(
        Enum(TokenKind, name="token_kind"), nullable=False
    )
    # Polymorphic reference to what earned/consumed the tokens (e.g. a review).
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
