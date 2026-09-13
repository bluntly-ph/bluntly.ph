"""Seller rules that hold without a database (FR-4).

The seller flow is reinstated by the completion contract. Most of what makes
it trustworthy is decided before a row is written, so it is asserted here where
it runs on every machine rather than only behind `requires_db`:

* **Duplicate stores.** Two rows for one store split its rating in half. The
  name a reviewer types is normalised before the uniqueness constraint sees it,
  so casing and stray whitespace cannot mint a second seller.
* **The four dimensions.** FR-4 fixes their types: accuracy and completeness
  are binary judgements, service and packaging are graded 1-5, as is the
  overall rating, plus a would-recommend. A grade outside 1-5 or a missing
  dimension is refused at the boundary.
* **The public summary.** A store nobody has rated reports *no* numbers, not
  zeroes — "0% accurate" about a store with no reviews is a false statement.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.seller import SellerReviewCreate
from app.services.seller_service import normalize_seller_name, summarize_reviews


def _review(**overrides) -> dict:
    base = {
        "accuracy": True,
        "order_completeness": True,
        "customer_service": 5,
        "packaging_quality": 4,
        "overall_rating": 5,
        "would_recommend": True,
    }
    base.update(overrides)
    return base


def _row(**overrides) -> SimpleNamespace:
    """A stand-in with the attributes a SellerReview row exposes."""
    return SimpleNamespace(**_review(**overrides))


class TestSellerNameNormalisation:

    def test_case_and_surrounding_space_do_not_make_a_new_seller(self):
        assert normalize_seller_name("  Anker Official Store ") == normalize_seller_name(
            "anker official store")

    def test_internal_runs_of_whitespace_collapse(self):
        assert normalize_seller_name("Anker   Official\tStore") == "anker official store"

    def test_distinct_names_stay_distinct(self):
        assert normalize_seller_name("Anker Official") != normalize_seller_name(
            "Anker Official Store")

    def test_a_blank_name_is_refused(self):
        with pytest.raises(ValueError):
            normalize_seller_name("   ")


class TestSellerReviewValidation:

    def test_a_complete_review_is_accepted(self):
        review = SellerReviewCreate(**_review())
        assert review.overall_rating == 5

    @pytest.mark.parametrize("field", ["customer_service", "packaging_quality", "overall_rating"])
    @pytest.mark.parametrize("value", [0, 6])
    def test_graded_dimensions_are_one_to_five(self, field, value):
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(**{field: value}))

    @pytest.mark.parametrize("field", [
        "accuracy", "order_completeness", "customer_service",
        "packaging_quality", "overall_rating", "would_recommend",
    ])
    def test_every_dimension_is_required(self, field):
        data = _review()
        data.pop(field)
        with pytest.raises(ValidationError):
            SellerReviewCreate(**data)

    def test_a_binary_dimension_does_not_accept_a_grade(self):
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(accuracy=3))

    def test_the_comment_is_bounded(self):
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(comment="x" * 2001))


class TestSellerReviewContent:
    """The written half of a seller review: a title, prose, and photos.

    The composer caps the title at 30 characters; the API allows 200, the same
    split product reviews use, so a later copy change in the composer does not
    need a migration. Photos are rendered as image sources on the seller page,
    so they obey the same http(s)-only rule as every other user-supplied URL.
    """

    def test_the_title_is_optional(self):
        assert SellerReviewCreate(**_review()).title is None

    def test_the_title_is_bounded_at_200(self):
        assert SellerReviewCreate(**_review(title="x" * 200)).title == "x" * 200
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(title="x" * 201))

    def test_photos_default_to_none_attached(self):
        assert SellerReviewCreate(**_review()).photo_urls == []

    def test_a_photo_must_be_a_web_link(self):
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(photo_urls=["javascript:alert(1)"]))

    def test_at_most_four_photos(self):
        urls = [f"https://cdn.example.com/{i}.jpg" for i in range(5)]
        assert len(SellerReviewCreate(**_review(photo_urls=urls[:4])).photo_urls) == 4
        with pytest.raises(ValidationError):
            SellerReviewCreate(**_review(photo_urls=urls))


class TestSellerSummary:

    def test_a_store_with_no_reviews_reports_no_numbers(self):
        summary = summarize_reviews([])
        assert summary.review_count == 0
        assert summary.accuracy_rate is None
        assert summary.order_completeness_rate is None
        assert summary.recommend_rate is None
        assert summary.customer_service_average is None
        assert summary.packaging_quality_average is None
        assert summary.overall_average is None

    def test_rates_are_the_share_of_positive_answers(self):
        summary = summarize_reviews([
            _row(accuracy=True), _row(accuracy=False),
            _row(accuracy=True), _row(accuracy=True),
        ])
        assert summary.review_count == 4
        assert summary.accuracy_rate == 0.75

    def test_completeness_and_recommend_are_counted_independently(self):
        summary = summarize_reviews([
            _row(order_completeness=False, would_recommend=True),
            _row(order_completeness=True, would_recommend=False),
        ])
        assert summary.order_completeness_rate == 0.5
        assert summary.recommend_rate == 0.5

    def test_averages_are_means_of_the_graded_dimensions(self):
        summary = summarize_reviews([
            _row(customer_service=5, packaging_quality=2, overall_rating=4),
            _row(customer_service=3, packaging_quality=4, overall_rating=2),
        ])
        assert summary.customer_service_average == 4.0
        assert summary.packaging_quality_average == 3.0
        assert summary.overall_average == 3.0

    def test_the_star_breakdown_counts_every_overall_rating(self):
        summary = summarize_reviews([
            _row(overall_rating=5), _row(overall_rating=5), _row(overall_rating=1),
        ])
        assert summary.rating_distribution == {1: 1, 2: 0, 3: 0, 4: 0, 5: 2}

    def test_an_unrated_store_has_a_breakdown_of_zero_counts(self):
        # Counts, not rates: "no 5-star reviews" is true of a store nobody has
        # rated, where "0% accurate" would not be.
        assert summarize_reviews([]).rating_distribution == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_averages_are_rounded_for_display_not_truncated(self):
        summary = summarize_reviews([
            _row(overall_rating=5), _row(overall_rating=4), _row(overall_rating=4),
        ])
        assert summary.overall_average == 4.33
