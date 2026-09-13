"""Seller review schemas (FR-4).

The four dimensions carry FR-4's types at the boundary: accuracy and order
completeness are binary judgements, customer service and packaging are graded
1-5, as is the overall rating, alongside a would-recommend. The database holds
the same ranges as CHECK constraints (migration 0042); validating here as well
turns a bad request into a 422 with a field name instead of an IntegrityError.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SellerReviewCreate(BaseModel):
    #: true = matched the advertisement, false = not the same.
    accuracy: bool
    #: true = exact order, false = something missing.
    order_completeness: bool
    customer_service: int = Field(ge=1, le=5)
    packaging_quality: int = Field(ge=1, le=5)
    overall_rating: int = Field(ge=1, le=5)
    would_recommend: bool
    #: What was bought, when the reviewer says.
    product_id: uuid.UUID | None = None
    comment: str | None = Field(default=None, max_length=2000)


class SellerSummary(BaseModel):
    """The public aggregate for one store.

    Every figure is nullable, and null when there is nothing to aggregate. A
    store nobody has rated has no accuracy rate; reporting 0.0 would state that
    none of its orders matched the listing.
    """

    review_count: int = 0
    accuracy_rate: float | None = None
    order_completeness_rate: float | None = None
    recommend_rate: float | None = None
    customer_service_average: float | None = None
    packaging_quality_average: float | None = None
    overall_average: float | None = None
