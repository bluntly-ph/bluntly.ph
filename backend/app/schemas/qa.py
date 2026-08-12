"""Community Q&A schemas (FR-5).

Questions are product-scoped and directed at either other buyers or the seller.
Answer-level earning (`answers.earn_eligible`) stays unwired (ADR-006 / A5).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestionDirectedTo


class QuestionCreate(BaseModel):
    product_id: uuid.UUID
    body: str = Field(min_length=1, max_length=2000)
    directed_to: QuestionDirectedTo = QuestionDirectedTo.buyers


class AnswerCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class QAAuthor(BaseModel):
    """The public author fields a Q&A card needs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    trust_stage: int = 0
    trust_level_name: str | None = None
    # See FeedAuthor.reputation_score — the badge reads the same everywhere.
    reputation_score: Decimal = Decimal("0")


class AnswerOut(BaseModel):
    id: uuid.UUID
    answer_id: str | None = None
    body: str
    is_best_answer: bool = False
    is_first_responder: bool = False
    helpful_votes: int = 0
    created_at: datetime
    responder: QAAuthor | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_id: str | None = None
    product_id: uuid.UUID
    product_name: str | None = None
    body: str
    directed_to: QuestionDirectedTo
    best_answer_id: uuid.UUID | None = None
    answer_count: int = 0
    created_at: datetime
    asker: QAAuthor | None = None


class QuestionDetailOut(QuestionOut):
    answers: list[AnswerOut] = []
