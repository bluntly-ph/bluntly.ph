"""Community Q&A routes (FR-5) — product-scoped questions, answers, Best Answer."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.qa import (
    AnswerCreate,
    AnswerOut,
    QuestionCreate,
    QuestionDetailOut,
    QuestionOut,
)
from app.services import qa_service

router = APIRouter(prefix="/questions", tags=["qa"])


@router.post("", response_model=QuestionOut, status_code=201,
             summary="Ask a question about a product")
def ask_question(payload: QuestionCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> QuestionOut:
    return qa_service.create_question(db, user.id, payload)


@router.get("", response_model=list[QuestionOut], summary="List questions")
def list_questions(db: Session = Depends(get_db),
                   product_id: uuid.UUID | None = None,
                   limit: int = Query(30, ge=1, le=100)) -> list[QuestionOut]:
    return qa_service.list_questions(db, product_id=product_id, limit=min(limit, 100))


@router.get("/{question_id}", response_model=QuestionDetailOut,
            summary="Get a question with its answers")
def get_question(question_id: uuid.UUID, db: Session = Depends(get_db)) -> QuestionDetailOut:
    return qa_service.get_question_detail(db, question_id)


@router.post("/{question_id}/answers", response_model=AnswerOut, status_code=201,
             summary="Answer a question")
def answer_question(question_id: uuid.UUID, payload: AnswerCreate,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> AnswerOut:
    question = qa_service.get_question_or_404(db, question_id)
    return qa_service.create_answer(db, question, user.id, payload)


@router.post("/{question_id}/answers/{answer_id}/best", response_model=QuestionDetailOut,
             summary="Award Best Answer (asker only)")
def best_answer(question_id: uuid.UUID, answer_id: uuid.UUID,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> QuestionDetailOut:
    question = qa_service.get_question_or_404(db, question_id)
    return qa_service.mark_best_answer(db, question, answer_id, user.id)
