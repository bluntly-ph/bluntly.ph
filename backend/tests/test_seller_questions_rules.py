"""Seller questions (FR-4 seller Q&A, FR-5), checked without a database.

The owner's seller page draws a Questions tab: buyers ask the store ("how long
do you usually ship out products?") and the store answers under its own name
with its Claimed Profile mark. Questions were product-scoped only, so a
question now has exactly one subject — a product or a store — and an answer
records whether the store's claimed owner wrote it.

Two rules carry the integrity of it and are pinned here:

* Only the moderator-approved owner of a claimed store answers *as the seller*.
  Anyone else, including someone with a claim still pending, answers as a buyer.
* A store owner answering questions about their own store earns no First
  Responder badge — the same refusal as answering your own question.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.enums import QuestionDirectedTo, SellerClaimStatus
from app.models.qa import Answer, Question
from app.schemas.qa import AnswerOut, QuestionCreate, QuestionOut
from app.services.qa_service import (
    FIRST_RESPONDER_WINDOW,
    first_responder_eligible,
    is_seller_answer,
)
from tests.test_seller_api_contract import _routes

PRODUCT = uuid.uuid4()
SELLER = uuid.uuid4()


class TestAQuestionHasExactlyOneSubject:

    def test_a_product_question_is_unchanged(self):
        q = QuestionCreate(product_id=PRODUCT, body="Is it loud?")
        assert q.seller_id is None
        assert q.directed_to == QuestionDirectedTo.buyers

    def test_a_store_question_is_directed_at_the_seller(self):
        q = QuestionCreate(seller_id=SELLER, body="How fast do you ship?")
        assert q.product_id is None
        assert q.directed_to == QuestionDirectedTo.seller

    def test_a_question_about_nothing_is_refused(self):
        with pytest.raises(ValidationError):
            QuestionCreate(body="About what?")

    def test_a_question_about_both_is_refused(self):
        with pytest.raises(ValidationError):
            QuestionCreate(product_id=PRODUCT, seller_id=SELLER, body="Both?")

    def test_the_database_holds_the_same_rule(self):
        names = {c.name for c in Question.__table__.constraints}
        assert "ck_question_subject" in names
        assert Question.__table__.c.product_id.nullable is True


class TestWhoAnswersAsTheSeller:

    @staticmethod
    def _store(owner, status=SellerClaimStatus.claimed):
        return SimpleNamespace(claimed_by_id=owner, claim_status=status)

    def test_the_claimed_owner_answers_as_the_seller(self):
        owner = uuid.uuid4()
        assert is_seller_answer(self._store(owner), owner) is True

    def test_anyone_else_answers_as_a_buyer(self):
        assert is_seller_answer(self._store(uuid.uuid4()), uuid.uuid4()) is False

    def test_a_store_that_is_not_claimed_has_nobody_to_answer_for_it(self):
        owner = uuid.uuid4()
        assert is_seller_answer(self._store(owner, SellerClaimStatus.pending), owner) is False

    def test_a_product_question_has_no_seller(self):
        assert is_seller_answer(None, uuid.uuid4()) is False


class TestFirstResponder:

    HOUR = timedelta(hours=1)

    def test_the_first_answer_within_the_window_earns_it(self):
        assert first_responder_eligible(0, self.HOUR, answering_own=False,
                                        seller_answer=False) is True

    def test_a_store_answering_about_itself_does_not(self):
        assert first_responder_eligible(0, self.HOUR, answering_own=False,
                                        seller_answer=True) is False

    def test_answering_your_own_question_still_does_not(self):
        assert first_responder_eligible(0, self.HOUR, answering_own=True,
                                        seller_answer=False) is False

    def test_a_late_or_second_answer_does_not(self):
        late = FIRST_RESPONDER_WINDOW + timedelta(seconds=1)
        assert first_responder_eligible(0, late, answering_own=False, seller_answer=False) is False
        assert first_responder_eligible(1, self.HOUR, answering_own=False,
                                        seller_answer=False) is False


def test_an_answer_says_when_the_store_wrote_it():
    assert {"is_seller_answer", "seller_name"} <= set(AnswerOut.model_fields)
    assert Answer.__table__.c.is_seller_answer.server_default is not None


def test_a_store_question_serialises_without_a_product():
    out = QuestionOut(id=uuid.uuid4(), product_id=None, seller_id=SELLER,
                      seller_name="Jisulife Official Store", body="Shipping?",
                      directed_to=QuestionDirectedTo.seller, created_at=datetime.now(UTC))
    assert out.product_id is None
    assert out.seller_name == "Jisulife Official Store"


def test_questions_can_be_listed_by_store():
    route = _routes()[("GET", "/api/v1/questions")]
    assert "seller_id" in {p.name for p in route.dependant.query_params}
