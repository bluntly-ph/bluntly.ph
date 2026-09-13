"""Seller schemas (FR-4).

The four review dimensions carry FR-4's types at the boundary: accuracy and
order completeness are binary judgements, customer service and packaging are
graded 1-5, as is the overall rating, alongside a would-recommend. The database
holds the same ranges as CHECK constraints (migration 0042); validating here as
well turns a bad request into a 422 with a field name instead of an
IntegrityError.

The public seller shape exposes whether a store is claimed, never *who* claimed
it: that is an account id, and a reader deciding whether to trust a store does
not need it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Platform, SellerClaimStatus
from app.schemas.urls import web_url_or_none


class SellerCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    platform: Platform
    store_url: str | None = Field(default=None, max_length=2000)

    # A store link is rendered as an href on the seller page and in the
    # moderator's claim queue, so a `javascript:` URL here is script execution
    # in whichever session clicks it. http(s) only, via the shared rule every
    # other user-supplied URL uses (app/schemas/urls.py).
    @field_validator("store_url")
    @classmethod
    def _only_web_store_url(cls, value: str | None) -> str | None:
        return web_url_or_none(value, field="Store links")


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    platform: Platform
    store_url: str | None = None
    claim_status: SellerClaimStatus
    created_at: datetime


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


class SellerReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    product_id: uuid.UUID | None = None
    accuracy: bool
    order_completeness: bool
    customer_service: int
    packaging_quality: int
    overall_rating: int
    would_recommend: bool
    comment: str | None = None
    created_at: datetime


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


class SellerDetailOut(SellerOut):
    summary: SellerSummary


class SellerClaimCreate(BaseModel):
    #: What makes the claimant the owner. Free text, cross-checked by a
    #: moderator against the public listing.
    evidence: str = Field(min_length=1, max_length=4000)


class SellerClaimOut(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    seller_display_name: str | None = None
    status: SellerClaimStatus
    evidence: str | None = None
    decision_note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ClaimDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=2000)
