"""earn_eligible_votes (FR-6, fraud layer 7).

Gate votes are snapshotted at vote time: trust stage, trust score, account age,
probation, and the computed vote_weight. These snapshots are IMMUTABLE — gate
decisions stay auditable and immune to retroactive trust changes (Architecture
§4). This differs from equal-weight community *visibility* votes (on reviews).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import VoteDirection


class ReviewVote(Base, UUIDPrimaryKey, Timestamps):
    """Equal-weight community visibility vote on a published review (M2 slice 2).

    One vote per (review, voter); changing direction is an upsert. Feeds
    `reviews.helpful_votes/unhelpful_votes/wilson_score` and the author's
    `helpfulness_ratio`. Distinct from weighted gate votes below.
    """

    __tablename__ = "review_votes"
    __table_args__ = (
        UniqueConstraint("review_id", "voter_id", name="uq_review_vote_once"),
        Index("ix_review_votes_review_id", "review_id"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vote: Mapped[VoteDirection] = mapped_column(
        Enum(VoteDirection, name="vote_direction"), nullable=False
    )


class EarnEligibleVote(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "earn_eligible_votes"
    __table_args__ = (
        UniqueConstraint("review_id", "voter_id", name="uq_gate_vote_once"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    vote: Mapped[VoteDirection] = mapped_column(
        Enum(VoteDirection, name="vote_direction"), nullable=False
    )

    # --- Immutable snapshots captured at vote time ---
    vote_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    trust_stage_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_score_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    account_age_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    is_probation_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False)
