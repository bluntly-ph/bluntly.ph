"""Community Q&A schemas (FR-5).

Questions are product-scoped and directed at either other buyers or the seller.
Answer-level earning (`answers.earn_eligible`) stays unwired (ADR-006 / A5).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import QuestionDirectedTo


class QuestionCreate(BaseModel):
    """A question about exactly one subject: a product, or a store (0045)."""

    product_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    body: str = Field(min_length=1, max_length=2000)
    #: Defaults to the seller for a store question and to other buyers otherwise.
    directed_to: QuestionDirectedTo | None = None

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> QuestionCreate:
        if (self.product_id is None) == (self.seller_id is None):
            raise ValueError("A question is about a product or a store: give exactly one.")
        if self.directed_to is None:
            self.directed_to = (QuestionDirectedTo.seller if self.seller_id is not None
                                else QuestionDirectedTo.buyers)
        return self


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
    #: True when the store's claimed owner wrote this, on a store question.
    is_seller_answer: bool = False
    #: The store's name, set only on a seller answer, so it is shown as the store.
    seller_name: str | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_id: str | None = None
    #: Null for a question asked of a store.
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    seller_id: uuid.UUID | None = None
    seller_name: str | None = None
    body: str
    directed_to: QuestionDirectedTo
    best_answer_id: uuid.UUID | None = None
    answer_count: int = 0
    created_at: datetime
    asker: QAAuthor | None = None


class QuestionDetailOut(QuestionOut):
    answers: list[AnswerOut] = []
