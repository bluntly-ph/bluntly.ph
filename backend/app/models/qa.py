"""questions, answers (FR-5).

Best Answer (one per question) and First Responder badge (first answer < 24h).
`answers.earn_eligible` exists per the Data Dictionary but is intentionally
UNWIRED in this build (ADR-006 / A5: answer-level earning is out of scope).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import QuestionDirectedTo


class Question(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "questions"

    question_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    asker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    directed_to: Mapped[QuestionDirectedTo] = mapped_column(
        Enum(QuestionDirectedTo, name="question_directed_to"), nullable=False
    )
    # FK set once a Best Answer is awarded; use_alter avoids a create-order cycle.
    best_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="SET NULL", use_alter=True,
                   name="fk_questions_best_answer"),
    )
    is_removed: Mapped[bool] = mapped_column(default=False, server_default="false")

    answers: Mapped[list[Answer]] = relationship(
        back_populates="question", cascade="all, delete-orphan",
        foreign_keys="Answer.question_id",
    )


class Answer(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "answers"

    answer_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    responder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_best_answer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_first_responder: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    helpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unhelpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wilson_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=0, nullable=False, server_default="0"
    )

    # Present per Data Dictionary; NOT wired to any earning logic in this build.
    earn_eligible: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    question: Mapped[Question] = relationship(
        back_populates="answers", foreign_keys=[question_id]
    )
