"""Review-comment schemas (BUG-014)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import VoteDirection


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    # Present only on a reply. The service rejects a parent that is itself a
    # reply — threading is one level deep by design (see models/comment.py).
    parent_id: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        """`min_length` counts characters, so "   " passes it and posts blank.

        Strip first, then re-check, so the stored body is also trimmed.
        """
        value = value.strip()
        if not value:
            raise ValueError("A comment cannot be empty.")
        return value


class CommentAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    trust_stage: int | None = None
    trust_level_name: str | None = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    body: str
    helpful_votes: int
    unhelpful_votes: int
    is_removed: bool
    created_at: datetime
    author: CommentAuthor | None = None
    # The viewer's own vote, so the UI can show the pressed state without a
    # second round trip. None for signed-out readers and for un-voted comments.
    my_vote: VoteDirection | None = None
    replies: list[CommentOut] = Field(default_factory=list)


# `replies` refers to the class being defined, and `from __future__ import
# annotations` keeps every annotation a string, so the forward reference is only
# resolvable once the class exists.
CommentOut.model_rebuild()


class CommentVoteIn(BaseModel):
    vote: VoteDirection
