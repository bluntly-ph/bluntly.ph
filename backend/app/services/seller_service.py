"""Seller service (FR-4).

The rules that decide whether a seller is a duplicate, and what a store's
public numbers say, live here as plain functions so they are tested on every
machine (`tests/test_seller_rules.py`) rather than only behind a database.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.schemas.seller import SellerSummary

_WHITESPACE = re.compile(r"\s+")


def normalize_seller_name(name: str) -> str:
    """The key the `(platform, normalized_name)` uniqueness constraint sees.

    Casefolded with every run of whitespace collapsed to one space, so a
    reviewer typing "Anker  Official Store " finds the existing store instead
    of creating a second one and splitting its rating in half.
    """
    collapsed = _WHITESPACE.sub(" ", name).strip().casefold()
    if not collapsed:
        raise ValueError("A seller needs a name.")
    return collapsed


def summarize_reviews(reviews: Iterable[Any]) -> SellerSummary:
    """Aggregate seller reviews into the public summary.

    Rates are the share of positive answers; averages are the mean of the
    graded dimensions, rounded for display. With no reviews every figure is
    None rather than zero — see SellerSummary.
    """
    rows = list(reviews)
    count = len(rows)
    if count == 0:
        return SellerSummary(review_count=0)

    def rate(attribute: str) -> float:
        return round(sum(1 for row in rows if getattr(row, attribute)) / count, 4)

    def mean(attribute: str) -> float:
        return round(sum(getattr(row, attribute) for row in rows) / count, 2)

    return SellerSummary(
        review_count=count,
        accuracy_rate=rate("accuracy"),
        order_completeness_rate=rate("order_completeness"),
        recommend_rate=rate("would_recommend"),
        customer_service_average=mean("customer_service"),
        packaging_quality_average=mean("packaging_quality"),
        overall_average=mean("overall_rating"),
    )
