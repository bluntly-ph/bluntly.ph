"""Ratings run 0 to 5 in half steps, and zero is an answer.

Owner requirement, 2026-09-16, replacing the whole-stars-only assumption the
schema and the CHECK constraints carried (migration 0048). Two things have to
hold, and both are easy to lose in a refactor:

  * the API accepts 0, 0.5, 3.5, 4.5 and 5, and refuses anything off the step;
  * a 0 is stored and read back as a rating, not as a missing value.

The averages are checked too, because the point of half steps is lost if the
aggregate rounds them away.
"""

from __future__ import annotations

import pytest

from app.schemas.review import ReviewCreate, half_step
from app.schemas.seller import SellerReviewCreate
from tests.conftest import owned_photo_url, register_and_token, requires_db

ACCEPTED = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
REFUSED = [-0.5, -1, 0.25, 2.3, 4.75, 5.5, 6]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("value", ACCEPTED)
def test_half_step_accepts_every_step(value):
    assert half_step(value) == value


@pytest.mark.parametrize("value", REFUSED)
def test_half_step_refuses_everything_between(value):
    with pytest.raises(ValueError):
        half_step(value)


@pytest.mark.parametrize("value", [0, 0.5, 3.5, 4.5, 5])
def test_review_schema_takes_the_steps(value):
    import uuid

    payload = ReviewCreate(
        product_id=uuid.uuid4(),
        title="Fixture",
        discussion="Long enough to pass the composer's floor for a discussion.",
        verdict="it_depends",
        star_rating=value,
    )
    assert payload.star_rating == value


@pytest.mark.parametrize("value", [0, 0.5, 3.5, 4.5, 5])
def test_seller_schema_takes_the_steps(value):
    payload = SellerReviewCreate(
        accuracy=True,
        order_completeness=True,
        customer_service=4,
        packaging_quality=4,
        overall_rating=value,
        would_recommend=True,
    )
    assert payload.overall_rating == value


def test_seller_graded_dimensions_stay_whole_numbers():
    """The frame draws customer service and packaging as numbered chips."""
    with pytest.raises(ValueError):
        SellerReviewCreate(
            accuracy=True,
            order_completeness=True,
            customer_service=3.5,
            packaging_quality=4,
            overall_rating=4,
            would_recommend=True,
        )


@requires_db
@pytest.mark.parametrize("value", [0, 0.5, 3.5, 5])
def test_review_round_trips_a_half_step(client, value):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    prod = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Half Star Fixture {token[-10:]}-{value}", "category": "electronics"},
    )
    assert prod.status_code == 201, prod.text

    created = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "product_id": prod.json()["id"],
            "title": "Half step",
            "discussion": "Stored as given, read back as given.",
            "verdict": "it_depends",
            "star_rating": value,
            "photo_url": owned_photo_url(headers),
        },
    )
    assert created.status_code == 201, created.text
    assert float(created.json()["star_rating"]) == value

    # With the author's headers: a review sits unpublished until a moderator
    # decides on it, and an unpublished review is 404 to everyone else. That is
    # the publication gate working, not a rating problem.
    read_back = client.get(f"/api/v1/reviews/{created.json()['id']}", headers=headers)
    assert read_back.status_code == 200, read_back.text
    assert float(read_back.json()["star_rating"]) == value, "zero must survive as a rating"


@requires_db
def test_review_refuses_a_rating_between_steps(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    prod = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Off Step {token[-10:]}", "category": "electronics"},
    )
    created = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "product_id": prod.json()["id"],
            "title": "Off the step",
            "discussion": "The API should refuse this one.",
            "verdict": "hard_pass",
            "star_rating": 2.3,
        },
    )
    assert created.status_code == 422, created.text


def test_seller_summary_keeps_the_decimal_and_bars_the_halves():
    """A 4.5 belongs in the four-star bar, and the average keeps its decimal."""
    from types import SimpleNamespace

    from app.services.seller_service import summarize_reviews

    rows = [
        SimpleNamespace(
            accuracy=True,
            order_completeness=True,
            would_recommend=True,
            customer_service=4,
            packaging_quality=5,
            overall_rating=overall,
        )
        for overall in (4.5, 3.5, 5)
    ]
    summary = summarize_reviews(rows)
    assert summary.overall_average == pytest.approx(4.33, abs=0.01)
    assert summary.rating_distribution[4] == 1, "4.5 counts in the four-star bar"
    assert summary.rating_distribution[3] == 1, "3.5 counts in the three-star bar"
    assert summary.rating_distribution[5] == 1


def test_seller_summary_counts_a_zero_in_the_first_bar():
    from types import SimpleNamespace

    from app.services.seller_service import summarize_reviews

    rows = [
        SimpleNamespace(
            accuracy=False,
            order_completeness=False,
            would_recommend=False,
            customer_service=1,
            packaging_quality=1,
            overall_rating=0,
        )
    ]
    summary = summarize_reviews(rows)
    assert summary.overall_average == 0.0
    assert summary.rating_distribution[1] == 1
