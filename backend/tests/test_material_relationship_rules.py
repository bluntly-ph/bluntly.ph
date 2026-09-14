"""Disclosure of a material relationship (completion contract X.1), without a database.

A reviewer declares whether they bought the product themselves, received it
free or discounted, or are connected to the brand or seller. The declaration is
part of the review: public, and versioned like every other field, so an edit
that quietly drops "I got it free" leaves a record.

A review written before the question existed has no answer. That is stored as
NULL — "never asked" — rather than defaulted to "none", which would put words
in the author's mouth. The composer always asks; an older API client that does
not send the field is recorded as not asked.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import MaterialRelationship
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewOut, ReviewUpdate
from app.services.review_service import VERSIONED_FIELDS

BASE = {"product_id": str(uuid.uuid4()), "title": "Light and quiet",
        "discussion": "Used it daily for a month and it held up fine.",
        "verdict": "it_depends", "star_rating": 4}


def test_the_three_answers():
    assert [m.value for m in MaterialRelationship] == ["none", "free_or_discounted", "connected"]


def test_a_review_carries_the_answer():
    review = ReviewCreate(**BASE, material_relationship="free_or_discounted")
    assert review.material_relationship == MaterialRelationship.free_or_discounted


def test_a_client_that_does_not_ask_is_recorded_as_not_asked():
    assert ReviewCreate(**BASE).material_relationship is None


def test_an_answer_outside_the_three_is_refused():
    with pytest.raises(ValidationError):
        ReviewCreate(**BASE, material_relationship="paid_promotion")


def test_the_answer_is_public_editable_and_versioned():
    assert "material_relationship" in ReviewOut.model_fields
    assert "material_relationship" in ReviewUpdate.model_fields
    assert "material_relationship" in VERSIONED_FIELDS


def test_the_column_allows_reviews_that_were_never_asked():
    assert Review.__table__.c.material_relationship.nullable is True
