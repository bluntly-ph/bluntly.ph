"""review_comments + review_comment_votes (FR-9b, BUG-014).

Discussion under a published review. Distinct from Q&A `answers`, which hang off
a *product* question and carry Best Answer / First Responder semantics; a comment
carries none of that and never earns.

Threading is deliberately one level deep: a comment either sits at the top level
or replies to a top-level comment. Unbounded nesting has no design to render it
and turns the read query into a recursive walk for no product gain.

Removal is soft (`is_removed`) so a moderator action stays auditable and a reply
never loses its parent — the same posture as `reviews.is_removed`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import VoteDirection


class ReviewComment(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "review_comments"
    __table_args__ = (
        # The read path is always "every comment on this review, oldest first".
        Index("ix_review_comments_review_created", "review_id", "created_at"),
        Index("ix_review_comments_parent_id", "parent_id"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    # SET NULL rather than CASCADE, matching `reviews.author_id`: deleting an
    # account must not silently rewrite a conversation other people took part in.
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # A reply's parent. CASCADE: deleting a thread root takes its replies, which
    # is the only sane reading of a deleted parent.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_comments.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    helpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unhelpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    is_removed: Mapped[bool] = mapped_column(default=False, server_default="false")

    replies: Mapped[list[ReviewComment]] = relationship(
        back_populates="parent", cascade="all, delete-orphan",
    )
    parent: Mapped[ReviewComment | None] = relationship(
        back_populates="replies", remote_side="ReviewComment.id",
    )


class ReviewCommentVote(Base, UUIDPrimaryKey, Timestamps):
    """One vote per (comment, voter); changing direction is an upsert.

    Equal weight, like `ReviewVote` — comment votes order a discussion, they do
    not feed trust, ranking, or earnings, so none of the gate-vote snapshotting
    applies here.
    """

    __tablename__ = "review_comment_votes"
    __table_args__ = (
        UniqueConstraint("comment_id", "voter_id", name="uq_review_comment_vote_once"),
        Index("ix_review_comment_votes_comment_id", "comment_id"),
    )

    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vote: Mapped[VoteDirection] = mapped_column(
        Enum(VoteDirection, name="vote_direction"), nullable=False
    )
