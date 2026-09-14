"""Community Q&A service (FR-5, and FR-4's seller Q&A).

Questions about a product or about a store, with answers, a First Responder
badge (first answer within 24h), and a Best Answer the asker awards.
Answer-level earning stays unwired (ADR-006 / A5). Trust-score recompute on
Best Answer is left to the trust system; here we set the flags and award the
badges.

A store question (0045) is asked from the seller page. When the store's
moderator-approved owner answers it, the answer is marked as the seller's and
shown under the store's name; anyone else, including a claimant still waiting
for a moderator, answers as a buyer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models.enums import SellerClaimStatus
from app.models.product import Product
from app.models.qa import Answer, Question
from app.models.seller import Seller
from app.models.user import Badge, User, UserBadge
from app.schemas.qa import (
    AnswerCreate,
    AnswerOut,
    QAAuthor,
    QuestionCreate,
    QuestionDetailOut,
    QuestionOut,
)

FIRST_RESPONDER_WINDOW = timedelta(hours=24)


def is_seller_answer(seller: Any | None, responder_id: uuid.UUID) -> bool:
    """Whether this responder answers *as the store*.

    Only the owner a moderator approved — `claim_status == claimed` and
    `claimed_by_id` is them. A pending claim is a request, not ownership
    (FR-4), so a claimant waiting on a moderator answers as a buyer.
    """
    return (
        seller is not None
        and seller.claim_status == SellerClaimStatus.claimed
        and seller.claimed_by_id is not None
        and seller.claimed_by_id == responder_id
    )


def first_responder_eligible(prior_answers: int, age: timedelta, *,
                             answering_own: bool, seller_answer: bool) -> bool:
    """The First Responder rule: the first answer, inside the window.

    Refused when answering your own question (the self-dealing hole it used to
    have), and when a store answers a question about itself: a store replying
    to its own customers is the point of the feature, and a badge for it would
    reward the store for being asked.
    """
    return (prior_answers == 0 and age <= FIRST_RESPONDER_WINDOW
            and not answering_own and not seller_answer)


def _author(user: User | None) -> QAAuthor | None:
    if user is None:
        return None
    return QAAuthor(
        id=user.id, username=user.username, display_name=user.display_name,
        trust_stage=user.trust_stage, trust_level_name=user.trust_level_name,
    )


def _answer_out(answer: Answer, responder: User | None,
                seller: Seller | None = None) -> AnswerOut:
    return AnswerOut(
        id=answer.id, answer_id=answer.answer_id, body=answer.body,
        is_best_answer=answer.is_best_answer, is_first_responder=answer.is_first_responder,
        helpful_votes=answer.helpful_votes, created_at=answer.created_at,
        responder=_author(responder),
        is_seller_answer=bool(answer.is_seller_answer),
        seller_name=(seller.display_name
                     if answer.is_seller_answer and seller is not None else None),
    )


def _award_badge(db: Session, user_id: uuid.UUID | None, badge_key: str) -> None:
    if user_id is None:
        return
    badge = db.scalar(select(Badge).where(Badge.badge_id == badge_key))
    if badge is None:
        return
    already = db.scalar(
        select(UserBadge).where(UserBadge.user_id == user_id, UserBadge.badge_id == badge.id)
    )
    if already is None:
        db.add(UserBadge(user_id=user_id, badge_id=badge.id))


def get_question_or_404(db: Session, question_id: uuid.UUID) -> Question:
    q = db.get(Question, question_id)
    if q is None or q.is_removed:
        raise NotFoundError("Question not found.", code="question_not_found")
    return q


def create_question(db: Session, asker_id: uuid.UUID, payload: QuestionCreate) -> QuestionOut:
    product = seller = None
    if payload.product_id is not None:
        product = db.get(Product, payload.product_id)
        if product is None:
            raise NotFoundError("Product not found.", code="product_not_found")
    else:
        seller = db.get(Seller, payload.seller_id)
        if seller is None:
            raise NotFoundError("Seller not found.", code="seller_not_found")
    q = Question(
        product_id=payload.product_id, seller_id=payload.seller_id, asker_id=asker_id,
        body=payload.body, directed_to=payload.directed_to,
        question_id=f"qst_{uuid.uuid4().hex[:10]}",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return QuestionOut(
        id=q.id, question_id=q.question_id, product_id=q.product_id,
        product_name=product.canonical_name if product is not None else None,
        seller_id=q.seller_id,
        seller_name=seller.display_name if seller is not None else None,
        body=q.body, directed_to=q.directed_to,
        best_answer_id=None, answer_count=0, created_at=q.created_at,
        asker=_author(db.get(User, asker_id)),
    )


def list_questions(
    db: Session, *, product_id: uuid.UUID | None = None,
    seller_id: uuid.UUID | None = None, q: str | None = None, limit: int = 30,
) -> list[QuestionOut]:
    stmt = select(Question).where(Question.is_removed.is_(False))
    if product_id is not None:
        stmt = stmt.where(Question.product_id == product_id)
    if seller_id is not None:
        stmt = stmt.where(Question.seller_id == seller_id)
    # Free-text search, for the Questions tab on /search.
    #
    # The wording, the product and the store are all matched: someone searching
    # "jisulife" means the product or the store at least as often as the
    # phrasing of a question, and the card's headline is that subject.
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        stmt = stmt.where(
            or_(
                Question.body.ilike(like),
                Question.product_id.in_(
                    select(Product.id).where(Product.canonical_name.ilike(like)),
                ),
                Question.seller_id.in_(
                    select(Seller.id).where(Seller.display_name.ilike(like)),
                ),
            ),
        )
    questions = list(db.scalars(stmt.order_by(Question.created_at.desc()).limit(limit)))
    if not questions:
        return []

    asker_ids = {q.asker_id for q in questions if q.asker_id is not None}
    product_ids = {q.product_id for q in questions if q.product_id is not None}
    seller_ids = {q.seller_id for q in questions if q.seller_id is not None}
    q_ids = [q.id for q in questions]
    askers = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(asker_ids)))}
        if asker_ids else {}
    )
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids else {}
    )
    sellers = (
        {s.id: s for s in db.scalars(select(Seller).where(Seller.id.in_(seller_ids)))}
        if seller_ids else {}
    )
    counts = dict(
        db.execute(
            select(Answer.question_id, func.count(Answer.id))
            .where(Answer.question_id.in_(q_ids))
            .group_by(Answer.question_id)
        ).all()
    )
    return [
        QuestionOut(
            id=q.id, question_id=q.question_id, product_id=q.product_id,
            product_name=(products[q.product_id].canonical_name
                          if q.product_id in products else None),
            seller_id=q.seller_id,
            seller_name=sellers[q.seller_id].display_name if q.seller_id in sellers else None,
            body=q.body, directed_to=q.directed_to, best_answer_id=q.best_answer_id,
            answer_count=counts.get(q.id, 0), created_at=q.created_at,
            asker=_author(askers.get(q.asker_id)),
        )
        for q in questions
    ]


def get_question_detail(db: Session, question_id: uuid.UUID) -> QuestionDetailOut:
    q = get_question_or_404(db, question_id)
    answers = list(
        db.scalars(
            select(Answer)
            .where(Answer.question_id == q.id)
            .order_by(
                Answer.is_best_answer.desc(),
                Answer.wilson_score.desc(),
                Answer.created_at.asc(),
            )
        )
    )
    responder_ids = {a.responder_id for a in answers if a.responder_id is not None}
    responders = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(responder_ids)))}
        if responder_ids else {}
    )
    product = db.get(Product, q.product_id) if q.product_id else None
    seller = db.get(Seller, q.seller_id) if q.seller_id else None
    asker = db.get(User, q.asker_id) if q.asker_id else None
    return QuestionDetailOut(
        id=q.id, question_id=q.question_id, product_id=q.product_id,
        product_name=product.canonical_name if product else None,
        seller_id=q.seller_id, seller_name=seller.display_name if seller else None,
        body=q.body, directed_to=q.directed_to, best_answer_id=q.best_answer_id,
        answer_count=len(answers), created_at=q.created_at, asker=_author(asker),
        answers=[_answer_out(a, responders.get(a.responder_id), seller) for a in answers],
    )


def create_answer(
    db: Session, question: Question, responder_id: uuid.UUID, payload: AnswerCreate,
) -> AnswerOut:
    prior = db.scalar(
        select(func.count(Answer.id)).where(Answer.question_id == question.id)
    )
    age = datetime.now(UTC) - question.created_at
    seller = db.get(Seller, question.seller_id) if question.seller_id else None
    seller_answer = is_seller_answer(seller, responder_id)
    # Answering your own question is allowed - somebody who finds the answer
    # and comes back to share it is doing exactly what the board is for. What
    # is not allowed is being paid for it: without this, asking a question and
    # answering it a second later awards yourself the first-responder badge,
    # repeatably, one new question at a time. See first_responder_eligible.
    is_first = first_responder_eligible(
        prior or 0, age, answering_own=responder_id == question.asker_id,
        seller_answer=seller_answer)

    answer = Answer(
        question_id=question.id, responder_id=responder_id, body=payload.body,
        answer_id=f"ans_{uuid.uuid4().hex[:10]}", is_first_responder=is_first,
        is_seller_answer=seller_answer,
    )
    db.add(answer)
    if is_first:
        _award_badge(db, responder_id, "first_responder")
    db.commit()
    db.refresh(answer)
    return _answer_out(answer, db.get(User, responder_id), seller)


def mark_best_answer(
    db: Session, question: Question, answer_id: uuid.UUID, asker_id: uuid.UUID,
) -> QuestionDetailOut:
    if question.asker_id != asker_id:
        raise ForbiddenError(
            "Only the person who asked can pick the best answer.",
            code="not_question_owner",
        )
    answer = db.get(Answer, answer_id)
    if answer is None or answer.question_id != question.id:
        raise NotFoundError("Answer not found.", code="answer_not_found")
    # The asker picks the best answer, so without this the asker can pick their
    # own and award themselves the badge. The other half of the same hole as
    # the first-responder check in create_answer.
    if answer.responder_id == asker_id:
        raise ForbiddenError(
            "You cannot mark your own answer as the best one.",
            code="cannot_pick_own_answer",
        )

    if question.best_answer_id and question.best_answer_id != answer.id:
        previous = db.get(Answer, question.best_answer_id)
        if previous is not None:
            previous.is_best_answer = False
    answer.is_best_answer = True
    question.best_answer_id = answer.id
    _award_badge(db, answer.responder_id, "best_answer")
    db.commit()
    return get_question_detail(db, question.id)
